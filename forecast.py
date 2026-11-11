import argparse
import csv
from datetime import date
import html
import json
import math
from pathlib import Path

DATA = Path(__file__).resolve().parent / 'data'

def load_rows(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def predict(origin, destination, day, price, forecast_path=None, routes_path=None):
    origin, destination = origin.strip().upper(), destination.strip().upper()
    try:
        day = date.fromisoformat(day).isoformat()
    except ValueError as exc:
        raise ValueError('Дата должна иметь формат ГГГГ-ММ-ДД.') from exc
    if not math.isfinite(price) or price < 0:
        raise ValueError('Цена должна быть конечным неотрицательным числом.')
    route = origin + '-' + destination
    routes = load_rows(routes_path or DATA / 'routes.csv')
    info = next((r for r in routes if r['route'] == route), None)
    if info is None:
        raise ValueError('Неизвестный маршрут. Доступны: ' + ', '.join(r['route'] for r in routes))
    rows = load_rows(forecast_path or DATA / 'my_forecast.csv')
    matches = [r for r in rows if r['route'] == route and r['date'] == day]
    if not matches:
        raise ValueError('На эту дату нет прогноза. Доступный период: 01.06-01.07.2026.')
    if len(matches) != 1:
        raise ValueError('В данных найдено несколько строк одного рейса.')
    row = matches[0]
    seats = int(row['seats'])
    if seats < 0:
        raise ValueError('Количество мест в данных не может быть отрицательным.')
    base, sensitivity = float(info['base_price']), float(info['price_sensitivity'])
    quantiles = {f'{i/10:.1f}': float(row[f'{i/10:.1f}_base_demand']) - sensitivity * (price - base) for i in range(1, 10)}
    if not all(math.isfinite(x) for x in quantiles.values()):
        raise ValueError('Прогноз содержит некорректные значения.')
    demand = quantiles['0.5']
    sold = min(seats, max(0, demand))
    return {'route': route, 'name': info['name'], 'date': day, 'price': price,
            'base_price': base, 'price_min': float(info['price_min']), 'price_max': float(info['price_max']),
            'seats': seats, 'demand': demand, 'sales': sold, 'free_after_forecast': seats - sold,
            'quantiles': quantiles}

def write_chart(result, path):
    """Квантильная кривая CDF: без догадок о плотности и неизвестных хвостах."""
    vals = list(result['quantiles'].values())
    low, high = min(vals + [0]), max(vals + [result['seats'], 1])
    margin = max((high-low)*.08, 1)
    low, high = low-margin, high+margin
    def x(v): return 90 + 790 * (v-low)/(high-low)
    def y(q): return 380 - 300*q
    points = ' '.join(f'{x(v):.2f},{y(i/10):.2f}' for i,v in enumerate(vals,1))
    title = html.escape(f"{result['name']} • {result['date']} • {result['price']:,.0f} ₽")
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 500"><rect width="960" height="500" fill="#f5f8fc"/><g font-family="Arial,sans-serif" fill="#17324d"><text x="40" y="35" font-size="20">{title}</text>',
         '<text x="40" y="62" font-size="14">Вероятность, что спрос не превысит значение по горизонтали</text>']
    for i in range(1,10):
        q=i/10
        s.append(f'<path d="M90 {y(q)} H880" stroke="#dce3ea"/><text x="48" y="{y(q)+5}" font-size="13">{i*10}%</text>')
    s.append(f'<polyline points="{points}" fill="none" stroke="#2471ce" stroke-width="3"/>')
    for i,v in enumerate(vals,1):
        s.append(f'<circle cx="{x(v)}" cy="{y(i/10)}" r="4" fill="#2471ce"/>')
    for value,color,label,offset in [(result['seats'],'#d55236','Мест',0),(result['demand'],'#23885a','Медиана',20)]:
        s.append(f'<path d="M{x(value)} 85 V390" stroke="{color}" stroke-dasharray="5 5"/><text x="{max(90,min(780,x(value)+5))}" y="{90+offset}" fill="{color}" font-size="13">{label}: {value:.1f}</text>')
    for i in range(6):
        v=low+(high-low)*i/5
        s.append(f'<text x="{x(v)}" y="410" text-anchor="middle" font-size="13">{v:.0f}</text>')
    s.append('<text x="90" y="445" font-size="14">Спрос, человек (до ограничения по местам)</text><text x="90" y="475" font-size="12">Между соседними квантилями — 10% вероятности; хвосты по 10% не восстановлены.</text></g></svg>')
    Path(path).write_text(''.join(s),encoding='utf-8')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from',dest='origin',required=True,help='Код отправления, например MOW')
    parser.add_argument('--to',dest='destination',required=True,help='Код назначения, например AER')
    parser.add_argument('--date',required=True)
    parser.add_argument('--price',required=True,type=float,help='Рубли')
    parser.add_argument('--forecast',type=Path,default=DATA/'my_forecast.csv')
    parser.add_argument('--routes',type=Path,default=DATA/'routes.csv')
    parser.add_argument('--chart',type=Path,help='Сохранить квантильный график в SVG')
    parser.add_argument('--json',action='store_true')
    args=parser.parse_args()
    try:
        r=predict(args.origin,args.destination,args.date,args.price,args.forecast,args.routes)
        if args.chart: write_chart(r,args.chart)
    except (ValueError, OSError, KeyError) as exc:
        parser.error(str(exc))
    if args.json:
        print(json.dumps(r,ensure_ascii=False,indent=2))
    else:
        print(f"{r['name']} | {r['date']} | {r['price']:,.2f} ₽")
        print(f"Всего мест: {r['seats']}\nЖелают (медиана): {r['demand']:.2f}\nКупят: {r['sales']:.2f}\nСвободно после прогнозных продаж: {r['free_after_forecast']:.2f}")
        print('Это прогноз, фактические бронирования в исходных данных отсутствуют.')
        if not r['price_min'] <= r['price'] <= r['price_max']:
            print('Цена вне диапазона оптимизации маршрута: результат является экстраполяцией.')
        if args.chart: print('График:',args.chart)

if __name__=='__main__': main()
