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
            return None, 'Empty response from BelarusBank API'

        for branch in data:
            usd_out_str = branch.get('USD_out')
            if usd_out_str:
                try:
                    usd_rate = Decimal(usd_out_str.replace(',', '.'))
                    usd_rate = usd_rate.quantize(Decimal('0.0001'))
                    return usd_rate, None
                except (ValueError, TypeError):
                    continue

        return None, 'USD rate not found in any branch response'

    except Exception as e:
        return None, f'BelarusBank error: {str(e)}'

def fetch_usd_rate_from_nbrb():
    try:
        url = 'https://api.nbrb.by/exrates/rates/431'
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        usd_rate = Decimal(str(data.get('Cur_OfficialRate')))
        usd_rate = usd_rate.quantize(Decimal('0.0001'))
        
        return usd_rate, None
    except Exception as e:
        return None, f'NBRB error: {str(e)}'

def fetch_usd_rate_from_national_bank():
    try:
        url = 'https://www.nbrb.by/api/exrates/rates/431'
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        usd_rate = Decimal(str(data.get('Cur_OfficialRate')))
        usd_rate = usd_rate.quantize(Decimal('0.0001'))
        
        return usd_rate, None
    except Exception as e:
        return None, f'NationalBank error: {str(e)}'

def fetch_usd_rate_from_cbr():
    try:
        url = 'https://www.cbr-xml-daily.ru/daily_json.js'
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        usd_rate = Decimal(str(data['Valute']['USD']['Value']))
        usd_rate = usd_rate.quantize(Decimal('0.0001'))
        
        return usd_rate, None
    except Exception as e:
        return None, f'CBR error: {str(e)}'

def fetch_usd_rate_from_any_source():
    sources = [
        ('BelarusBank', fetch_usd_rate_from_belarusbank),
        ('NBRB', fetch_usd_rate_from_nbrb),
        ('NationalBank', fetch_usd_rate_from_national_bank),
        ('CBR', fetch_usd_rate_from_cbr),
    ]
    
    for source_name, source_func in sources:
        usd_rate, error = source_func()
        
        if usd_rate is not None:
            current_app.logger.info(f'Successfully fetched USD rate from {source_name}: {usd_rate}')
            return usd_rate, None
        else:
            current_app.logger.warning(f'Failed to fetch from {source_name}: {error}')
            continue
    
    return None, 'All USD rate sources failed'

def update_plan_rates(plan):
    updated = False
    error_message = None
    usd_rate_result = None
    cost_result = None
    
    if plan.usd_rate is None or plan.usd_rate <= 0:
        usd_rate, error = fetch_usd_rate_from_any_source()
        
        if usd_rate is None:
            error_message = f'Failed to fetch USD rate: {error}'
            current_app.logger.error(f'Cannot update USD rate for plan_id={plan.id}: {error_message}')
            return None, None, error_message
        else:
            plan.usd_rate = usd_rate
            updated = True
            current_app.logger.info(f'USD rate set for plan_id={plan.id}: {usd_rate}')
    
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
    
    usd_rate, error = fetch_usd_rate_from_any_source()
    
    if usd_rate is None:
        return None, error
    
    return usd_rate, None