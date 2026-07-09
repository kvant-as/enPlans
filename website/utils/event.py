import logging
from flask import current_app
from .currency_rates import get_usd_rate_with_fallback, update_plan_rates
from .plans import to_decimal_2, to_decimal_1, generate_unique_display_code
from website.models import Direction, Organization, Plan, Ticket, Indicator, Event, IndicatorUsage, Notification, TimeByMinsk
from .. import db

logger = logging.getLogger(__name__)

def parse_number_with_comma(value):
    """Преобразует строку с запятой в число"""
    if not value:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    try:
        cleaned = str(value).replace(',', '.')
        return int(float(cleaned))
    except (ValueError, TypeError):
        return 0

def process_event_data(current_plan, direction, event_type, form_data):
    usd_rate, error = get_usd_rate_with_fallback(current_plan)
    
    if error:
        current_app.logger.error(f'Error getting USD rate for plan_id={current_plan.id}: {error}')
        raise ValueError(f'Невозможно получить курс доллара: {error}')
    
    USD_RATE = usd_rate
    
    if current_plan.cost_per_toe_usd and float(current_plan.cost_per_toe_usd) > 0:
        COST_PER_TOE_USD = float(current_plan.cost_per_toe_usd)
    else:
        _, _, cost_error = update_plan_rates(current_plan)
        if cost_error:
            current_app.logger.error(f'Error getting cost per toe: {cost_error}')
            raise ValueError(f'Невозможно получить стоимость т.у.т.: {cost_error}')
        COST_PER_TOE_USD = float(current_plan.cost_per_toe_usd) if current_plan.cost_per_toe_usd else 260.0
    
    current_app.logger.info(f'Processing event data: plan_id={current_plan.id}, USD_RATE={USD_RATE}, COST_PER_TOE_USD={COST_PER_TOE_USD}')
    
    Volume = int(form_data.get('Volume')) if form_data.get('Volume') else None
    EffTut_raw = form_data.get('EffTut')
    EffTut = float(to_decimal_2(EffTut_raw))
    ExpectedQuarter = int(form_data.get('ExpectedQuarter')) if form_data.get('ExpectedQuarter') else None
    EffCurrYear = to_decimal_2(form_data.get('EffCurrYear'))
    name = form_data.get('name') or None
    
    is_double_effect = direction.is_econom and direction.is_increase
    
    if event_type == 'saving':
        EffRub = int(EffTut * COST_PER_TOE_USD * USD_RATE)
        
        if is_double_effect:
            return {
                'name': name,
                'Volume': Volume,
                'EffTut': to_decimal_2(EffTut),
                'EffRub': EffRub,
                'ExpectedQuarter': ExpectedQuarter,
                'EffCurrYear': EffCurrYear,
                'Payback': None,
                'ObchVolumeFin': 0,
                'VolumeFinCurrentYear': 0,
                'BudgetState': 0,
                'BudgetRep': 0,
                'BudgetLoc': 0,
                'BudgetOther': 0,
                'MoneyOwn': 0,
                'MoneyLoan': 0,
                'MoneyOther': 0,
                'is_econom': True,
                'is_increase': False,
                'is_double_effect': True
            }
        
        ObchVolumeFin = parse_number_with_comma(form_data.get('ObchVolumeFin'))
        BudgetState = parse_number_with_comma(form_data.get('BudgetState'))
        BudgetRep = parse_number_with_comma(form_data.get('BudgetRep'))
        BudgetLoc = parse_number_with_comma(form_data.get('BudgetLoc'))
        BudgetOther = parse_number_with_comma(form_data.get('BudgetOther'))
        MoneyOwn = parse_number_with_comma(form_data.get('MoneyOwn'))
        MoneyLoan = parse_number_with_comma(form_data.get('MoneyLoan'))
        MoneyOther = parse_number_with_comma(form_data.get('MoneyOther'))
        
        VolumeFinCurrentYear = BudgetState + BudgetRep + BudgetLoc + BudgetOther + MoneyOwn + MoneyLoan + MoneyOther
        
        Payback = None
        if EffRub > 0:
            payback_value = VolumeFinCurrentYear / EffRub
            if payback_value < 0.1 and payback_value > 0:
                payback_value = 0.1
            Payback = to_decimal_1(payback_value)
        
        return {
            'name': name,
            'Volume': Volume,
            'EffTut': to_decimal_2(EffTut),
            'EffRub': EffRub,
            'ExpectedQuarter': ExpectedQuarter,
            'EffCurrYear': EffCurrYear,
            'Payback': Payback,
            'ObchVolumeFin': ObchVolumeFin,
            'VolumeFinCurrentYear': VolumeFinCurrentYear,
            'BudgetState': BudgetState,
            'BudgetRep': BudgetRep,
            'BudgetLoc': BudgetLoc,
            'BudgetOther': BudgetOther,
            'MoneyOwn': MoneyOwn,
            'MoneyLoan': MoneyLoan,
            'MoneyOther': MoneyOther,
            'is_econom': True,
            'is_increase': False,
            'is_double_effect': False
        }
    
    if event_type == 'increase':
        BudgetState = parse_number_with_comma(form_data.get('BudgetState'))
        BudgetRep = parse_number_with_comma(form_data.get('BudgetRep'))
        BudgetLoc = parse_number_with_comma(form_data.get('BudgetLoc'))
        BudgetOther = parse_number_with_comma(form_data.get('BudgetOther'))
        MoneyOwn = parse_number_with_comma(form_data.get('MoneyOwn'))
        MoneyLoan = parse_number_with_comma(form_data.get('MoneyLoan'))
        MoneyOther = parse_number_with_comma(form_data.get('MoneyOther'))
        
        ObchVolumeFin = parse_number_with_comma(form_data.get('ObchVolumeFin'))
        VolumeFinCurrentYear = BudgetState + BudgetRep + BudgetLoc + BudgetOther + MoneyOwn + MoneyLoan + MoneyOther
        EffRub = parse_number_with_comma(form_data.get('EffRub'))
        
        Payback = None
        if EffRub > 0:
            payback_value = VolumeFinCurrentYear / EffRub
            if payback_value < 0.1 and payback_value > 0:
                payback_value = 0.1
            Payback = to_decimal_1(payback_value)
        
        return {
            'name': name,
            'Volume': Volume,
            'EffTut': to_decimal_2(EffTut),
            'EffRub': EffRub,
            'ExpectedQuarter': ExpectedQuarter,
            'EffCurrYear': EffCurrYear,
            'Payback': Payback,
            'ObchVolumeFin': ObchVolumeFin,
            'VolumeFinCurrentYear': VolumeFinCurrentYear,
            'BudgetState': BudgetState,
            'BudgetRep': BudgetRep,
            'BudgetLoc': BudgetLoc,
            'BudgetOther': BudgetOther,
            'MoneyOwn': MoneyOwn,
            'MoneyLoan': MoneyLoan,
            'MoneyOther': MoneyOther,
            'is_econom': False,
            'is_increase': True,
            'is_double_effect': False
        }

def create_event_record(current_plan, direction, event_data):
    current_app.logger.info(f'Creating event record: plan_id={current_plan.id}, direction_id={direction.id}')
    
    display_code = generate_unique_display_code(direction.code, current_plan.id, direction.id)
    is_corrected = current_plan.audit_time is not None
    is_local = current_plan.audit_time is None
    
    event = Event(
        id_direction=direction.id,
        id_plan=current_plan.id,
        display_code=display_code,
        name=event_data['name'],
        Volume=event_data['Volume'],
        EffTut=event_data['EffTut'],
        EffRub=event_data['EffRub'],
        ExpectedQuarter=event_data['ExpectedQuarter'],
        EffCurrYear=event_data['EffCurrYear'],
        Payback=event_data['Payback'],
        ObchVolumeFin=event_data['ObchVolumeFin'],
        VolumeFinCurrentYear=event_data['VolumeFinCurrentYear'],
        BudgetState=event_data['BudgetState'],
        BudgetRep=event_data['BudgetRep'],
        BudgetLoc=event_data['BudgetLoc'],
        BudgetOther=event_data['BudgetOther'],
        MoneyOwn=event_data['MoneyOwn'],
        MoneyLoan=event_data['MoneyLoan'],
        MoneyOther=event_data['MoneyOther'],
        is_local=is_local,
        is_corrected=is_corrected,
        is_econom=event_data['is_econom'],
        is_increase=event_data['is_increase']
    )
    
    current_app.logger.info(f'Event object created: direction_id={direction.id}, is_econom={event_data["is_econom"]}, is_increase={event_data["is_increase"]}')
    return event

def update_double_effect_payback(plan_id, direction_id):
    from sqlalchemy import and_
    
    current_app.logger.info(f'Updating double effect payback: plan_id={plan_id}, direction_id={direction_id}')
    
    saving_event = Event.query.filter(
        and_(
            Event.id_plan == plan_id,
            Event.id_direction == direction_id,
            Event.is_econom == True,
            Event.is_increase == False
        )
    ).first()
    
    increase_event = Event.query.filter(
        and_(
            Event.id_plan == plan_id,
            Event.id_direction == direction_id,
            Event.is_econom == False,
            Event.is_increase == True
        )
    ).first()
    
    if not saving_event:
        current_app.logger.warning(f'Saving event not found for plan_id={plan_id}, direction_id={direction_id}')
        return
    
    if not increase_event:
        current_app.logger.warning(f'Increase event not found for plan_id={plan_id}, direction_id={direction_id}')
        return
    
    current_app.logger.info(f'Found saving_event: EffRub={saving_event.EffRub}')
    current_app.logger.info(f'Found increase_event: EffRub={increase_event.EffRub}, VolumeFinCurrentYear={increase_event.VolumeFinCurrentYear}')
    
    total_eff_rub = (saving_event.EffRub or 0) + (increase_event.EffRub or 0)
    volume_fin = increase_event.VolumeFinCurrentYear or 0
    
    current_app.logger.info(f'Total EffRub: {total_eff_rub}, VolumeFinCurrentYear: {volume_fin}')
    
    MIN_PAYBACK = 0.1
    
    if total_eff_rub > 0:
        payback_value = volume_fin / total_eff_rub
        
        if payback_value < MIN_PAYBACK and payback_value > 0:
            current_app.logger.info(f'Payback value {payback_value} is less than minimum {MIN_PAYBACK}, setting to minimum')
            payback_value = MIN_PAYBACK
        
        payback = to_decimal_1(payback_value)
        increase_event.Payback = payback
        db.session.commit()
        current_app.logger.info(f'Double effect payback calculated and saved: {payback}')
    else:
        current_app.logger.warning(f'Total EffRub is zero, cannot calculate payback')