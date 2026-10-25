"""Bound object references; chat is an additional caller of the direct APIs."""
from uuid import uuid4
from roambot.domain.business_tools import resolve_reference


async def public_itineraries(executor):
    data = await executor.call('GET', '/itineraries')
    return data


def describe(trip):
    return {key: trip.get(key) for key in ('id', 'name', 'version', 'start_date', 'end_date', 'travel_mode', 'days', 'unassigned_ids')} | {
        'stops': [{'id': s['id'], 'name': s['place']['name']} for s in trip['stops']]}


async def execute(executor, name, args, message):
    if name == 'create_itinerary':
        result = await executor.call('POST', '/itineraries', {'name': args['name']})
        trip = result['itinerary']
        executor.context.update(itinerary_id=trip['id'], itinerary_version=trip['version'])
        return result | {'reply': f"已创建「{trip['name']}」。", 'effect': {'tool': 'open_itinerary', 'arguments': {'id': trip['id']}}}
    data = await public_itineraries(executor)
    trips = data['itineraries']
    target = resolve_reference(args.get('itinerary'), trips,
        focused=executor.context.get('itinerary_id') or data['current_id'])
    trip = (await executor.call('GET', '/itineraries/' + target['id']))['itinerary']
    expected = executor.context.get('itinerary_version') if executor.context.get('itinerary_id') == trip['id'] else None
    if expected and expected != trip['version']:
        raise ValueError('行程已变化，请刷新后重新发起操作。')
    path = '/itineraries/' + trip['id']
    if name == 'open_itinerary':
        return {'reply': f"已打开「{trip['name']}」。", 'effect': {'tool': 'open_itinerary', 'arguments': {'id': trip['id']}}}
    if name == 'show_itinerary_map':
        number = args.get('day_number')
        if number is not None and number > len(trip['days']):
            raise ValueError('这一天不在当前行程内。')
        chosen = trip['days'][number-1] if number else next((d for d in trip['days']
            if d['date'] == args.get('day') or (not args.get('day') and d['stop_ids'])), None)
        if chosen is None or not chosen['stop_ids']:
            raise ValueError('这一天还没有安排地点。')
        if args.get('day') and chosen['date'] != args['day']:
            raise ValueError('指定日期与第几天不一致。')
        return {'reply': f"已打开{chosen['date']}的行程地图。", 'effect': {
            'tool': 'show_itinerary_map', 'arguments': {'itinerary_id': trip['id'], 'date': chosen['date']}}}
    if name == 'add_to_itinerary':
        place = resolve_reference(args.get('place'), await executor.places(), focused=executor.context.get('focused_id'))
        if executor.context.get('page') == '/favorites': body = {'favorite_id': place['id']}
        else: body = {'place_id': place['id'], **({'source_job_id': executor.context['discovery_job_id']}
            if executor.context.get('discovery_job_id') else {'history_id': executor.context.get('history_id')})}
        result = await executor.call('POST', path+'/stops', body)
        reply = f"已把{place['name']}加入「{trip['name']}」。"
    elif name == 'edit_itinerary':
        quote = args.pop('date_quote', None)
        if args.get('start_date') or args.get('end_date'):
            if not quote or not any(quote in text for text in [message]+[m['content'] for m in executor.context.get('conversation', []) if m['role']=='user']):
                raise ValueError('行程日期需要明确原文。')
        body = {k: v for k, v in args.items() if k != 'itinerary'} | {'version': trip['version']}
        result = await executor.call('PATCH', path, body); reply = '行程设置已保存。'
    elif name in {'move_itinerary_stop', 'remove_itinerary_stop'}:
        place = resolve_reference(args.get('place'), [{'id': s['id'], 'name': s['place']['name']} for s in trip['stops']])
        if name == 'remove_itinerary_stop':
            result = await executor.call('DELETE', path+'/stops/'+place['id']+'?version='+str(trip['version']))
            reply = f"已从行程移出{place['name']}。"
        else:
            day = args.get('day')
            if day:
                quote = args.get('date_quote')
                if not quote or not any(quote in text for text in [message]+[m['content'] for m in executor.context.get('conversation', []) if m['role']=='user']):
                    raise ValueError('移动日期需要明确原文。')
            if day and day not in {d['date'] for d in trip['days']}: raise ValueError('日期不在当前行程内。')
            days = [{'date': d['date'], 'stop_ids': [s for s in d['stop_ids'] if s != place['id']]} for d in trip['days']]
            unassigned = [s for s in trip['unassigned_ids'] if s != place['id']]
            into = next(d['stop_ids'] for d in days if d['date']==day) if day else unassigned
            into.insert(min(len(into), args['position']-1), place['id'])
            result = await executor.call('PUT', path+'/order', {'version': trip['version'], 'days': days, 'unassigned_ids': unassigned})
            reply = '顺序已保存，路线待更新。'
    else:
        result = await executor.call('POST', path+'/generate', {'version': trip['version'], 'optimize': args.get('optimize', False), 'request_id': str(uuid4())})
        reply = '已自动安排行程。' if args.get('optimize') else '已按当前顺序更新路线。'
    updated = result['itinerary']
    executor.context.update(itinerary_id=updated['id'], itinerary_version=updated['version'])
    return result | {'reply': reply}
