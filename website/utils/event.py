from flask import current_app
from .currency_rates import get_usd_rate_with_fallback, update_plan_rates
from .plans import to_decimal_2, to_decimal_1, generate_unique_display_code
from website.models import Direction, Organization, Plan, Ticket, Indicator, Event, IndicatorUsage, Notification, TimeByMinsk

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
                'VolumeFin': 0,
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
        
        BudgetState = int(form_data.get('BudgetState')) if form_data.get('BudgetState') else 0
        BudgetRep = int(form_data.get('BudgetRep')) if form_data.get('BudgetRep') else 0
        BudgetLoc = int(form_data.get('BudgetLoc')) if form_data.get('BudgetLoc') else 0
        BudgetOther = int(form_data.get('BudgetOther')) if form_data.get('BudgetOther') else 0
        MoneyOwn = int(form_data.get('MoneyOwn')) if form_data.get('MoneyOwn') else 0
        MoneyLoan = int(form_data.get('MoneyLoan')) if form_data.get('MoneyLoan') else 0
        MoneyOther = int(form_data.get('MoneyOther')) if form_data.get('MoneyOther') else 0
        
        VolumeFin = BudgetState + BudgetRep + BudgetLoc + BudgetOther + MoneyOwn + MoneyLoan + MoneyOther
        
        Payback = None
        if EffRub > 0:
            payback_value = VolumeFin / EffRub
            Payback = to_decimal_1(payback_value)
        
        return {
            'name': name,
            'Volume': Volume,
            'EffTut': to_decimal_2(EffTut),
            'EffRub': EffRub,
            'ExpectedQuarter': ExpectedQuarter,
            'EffCurrYear': EffCurrYear,
            'Payback': Payback,
            'VolumeFin': VolumeFin,
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
        if is_double_effect:
            BudgetState = int(form_data.get('BudgetState')) if form_data.get('BudgetState') else 0
            BudgetRep = int(form_data.get('BudgetRep')) if form_data.get('BudgetRep') else 0
            BudgetLoc = int(form_data.get('BudgetLoc')) if form_data.get('BudgetLoc') else 0
            BudgetOther = int(form_data.get('BudgetOther')) if form_data.get('BudgetOther') else 0
            MoneyOwn = int(form_data.get('MoneyOwn')) if form_data.get('MoneyOwn') else 0
            MoneyLoan = int(form_data.get('MoneyLoan')) if form_data.get('MoneyLoan') else 0
            MoneyOther = int(form_data.get('MoneyOther')) if form_data.get('MoneyOther') else 0
            
            VolumeFin = BudgetState + BudgetRep + BudgetLoc + BudgetOther + MoneyOwn + MoneyLoan + MoneyOther
            EffRub = int(EffTut * COST_PER_TOE_USD * USD_RATE)
            
            return {
                'name': name,
                'Volume': Volume,
                'EffTut': to_decimal_2(EffTut),
                'EffRub': EffRub,
                'ExpectedQuarter': ExpectedQuarter,
                'EffCurrYear': EffCurrYear,
                'Payback': None,
                'VolumeFin': VolumeFin,
                'BudgetState': BudgetState,
                'BudgetRep': BudgetRep,
                'BudgetLoc': BudgetLoc,
                'BudgetOther': BudgetOther,
                'MoneyOwn': MoneyOwn,
                'MoneyLoan': MoneyLoan,
                'MoneyOther': MoneyOther,
                'is_econom': False,
                'is_increase': True,
                'is_double_effect': True
            }
        
        BudgetState = int(form_data.get('BudgetState')) if form_data.get('BudgetState') else 0
        BudgetRep = int(form_data.get('BudgetRep')) if form_data.get('BudgetRep') else 0
        BudgetLoc = int(form_data.get('BudgetLoc')) if form_data.get('BudgetLoc') else 0
        BudgetOther = int(form_data.get('BudgetOther')) if form_data.get('BudgetOther') else 0
        MoneyOwn = int(form_data.get('MoneyOwn')) if form_data.get('MoneyOwn') else 0
        MoneyLoan = int(form_data.get('MoneyLoan')) if form_data.get('MoneyLoan') else 0
        MoneyOther = int(form_data.get('MoneyOther')) if form_data.get('MoneyOther') else 0
        
        VolumeFin = BudgetState + BudgetRep + BudgetLoc + BudgetOther + MoneyOwn + MoneyLoan + MoneyOther
        EffRub = int(EffTut * COST_PER_TOE_USD * USD_RATE)
        
        Payback = None
        if EffRub > 0:
            payback_value = VolumeFin / EffRub
            Payback = to_decimal_1(payback_value)
        
        return {
            'name': name,
            'Volume': Volume,
            'EffTut': to_decimal_2(EffTut),
            'EffRub': EffRub,
            'ExpectedQuarter': ExpectedQuarter,
            'EffCurrYear': EffCurrYear,
            'Payback': Payback,
            'VolumeFin': VolumeFin,
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
        VolumeFin=event_data['VolumeFin'],
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
    
    current_app.logger.debug(f'Found saving_event: EffRub={saving_event.EffRub}')
    current_app.logger.debug(f'Found increase_event: EffRub={increase_event.EffRub}, VolumeFin={increase_event.VolumeFin}')
    
    total_eff_rub = (saving_event.EffRub or 0) + (increase_event.EffRub or 0)
    volume_fin = increase_event.VolumeFin or 0
    
    current_app.logger.debug(f'Total EffRub: {total_eff_rub}, VolumeFin: {volume_fin}')
    
    if total_eff_rub > 0:
        payback_value = volume_fin / total_eff_rub
        payback = to_decimal_1(payback_value)
        increase_event.Payback = payback
        db.session.commit()
        current_app.logger.info(f'Double effect payback calculated and saved: {payback}')
    else:
        current_app.logger.warning(f'Total EffRub is zero, cannot calculate payback')