import requests
from decimal import Decimal
from flask import current_app

def fetch_usd_rate_from_belarusbank():
    try:
        url = 'https://belarusbank.by/api/kursExchange'
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if not data:
            error_msg = 'Empty response from BelarusBank API'
            current_app.logger.error(error_msg)
            return None, error_msg

        for branch in data:
            usd_out_str = branch.get('USD_out')
            if usd_out_str:
                try:
                    usd_rate = Decimal(usd_out_str.replace(',', '.'))
                    usd_rate = usd_rate.quantize(Decimal('0.0001'))
                    current_app.logger.info(f'USD rate fetched from BelarusBank: {usd_rate}')
                    return usd_rate, None
                except (ValueError, TypeError) as e:
                    current_app.logger.warning(f'Could not parse USD_out value: {usd_out_str}')
                    continue

        error_msg = 'USD rate not found in any branch response'
        current_app.logger.error(error_msg)
        return None, error_msg

    except requests.exceptions.Timeout:
        error_msg = 'Request to BelarusBank API timed out'
        current_app.logger.error(error_msg)
        return None, error_msg
    except requests.exceptions.ConnectionError as e:
        error_msg = f'Connection error to BelarusBank API: {str(e)}'
        current_app.logger.error(error_msg)
        return None, error_msg
    except requests.RequestException as e:
        error_msg = f'Request error fetching USD rate: {str(e)}'
        current_app.logger.error(error_msg)
        return None, error_msg
    except Exception as e:
        error_msg = f'Unexpected error fetching USD rate: {str(e)}'
        current_app.logger.exception(error_msg)
        return None, error_msg

def get_default_cost_per_toe_usd():
    return Decimal('260.00')

def update_plan_rates(plan):
    updated = False
    error_message = None
    usd_rate_result = None
    cost_result = None
    
    if plan.usd_rate is None or plan.usd_rate <= 0:
        usd_rate, error = fetch_usd_rate_from_belarusbank()
        
        if usd_rate is None:
            error_message = f'Failed to fetch USD rate: {error}'
            current_app.logger.error(f'Cannot update USD rate for plan_id={plan.id}: {error_message}')
            return None, None, error_message
        else:
            plan.usd_rate = usd_rate
            updated = True
            current_app.logger.info(f'USD rate set for plan_id={plan.id}: {usd_rate}')
    
    if plan.cost_per_toe_usd is None or plan.cost_per_toe_usd <= 0:
        plan.cost_per_toe_usd = get_default_cost_per_toe_usd()
        updated = True
        current_app.logger.info(f'Cost per toe set for plan_id={plan.id}: {plan.cost_per_toe_usd}')
    
    if updated:
        try:
            from website import db
            db.session.commit()
            current_app.logger.info(f'Rates saved for plan_id={plan.id}')
        except Exception as e:
            current_app.logger.error(f'Error saving rates to plan_id={plan.id}: {str(e)}')
            db.session.rollback()
            return None, None, str(e)
    
    usd_rate_result = float(plan.usd_rate) if plan.usd_rate else None
    cost_result = float(plan.cost_per_toe_usd) if plan.cost_per_toe_usd else None
    
    if usd_rate_result is None:
        return None, None, 'USD rate not available and could not be fetched'
    
    return usd_rate_result, cost_result, None

def get_usd_rate_with_fallback(plan):
    if plan.usd_rate and float(plan.usd_rate) > 0:
        return float(plan.usd_rate), None
    
    usd_rate, cost, error = update_plan_rates(plan)
    
    if usd_rate is None:
        return None, error
    
    return usd_rate, None