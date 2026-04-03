#!/usr/bin/env python3
"""
Finviz Market Dashboard — Standalone Public Web App
Run: pip install flask beautifulsoup4 lxml && python server.py
Access: http://localhost:5000
"""

import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, jsonify, send_from_directory
from bs4 import BeautifulSoup

app = Flask(__name__, static_folder='static')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# v=111 = Overview: No, Ticker, Company, Sector, Industry, Country, MktCap, P/E, Price, Change, Volume
# v=141 = Performance: No, Ticker, PerfWeek, ..., Price, Change, Volume
SCREENER_111 = 'https://finviz.com/screener.ashx?v=111&s=ta_topgainers&o=-volume&f=sh_price_o1'
SCREENER_141 = 'https://finviz.com/screener.ashx?v=141&s=ta_topgainers&o=-volume&f=sh_price_o1'
HOMEPAGE = 'https://finviz.com/'


def fetch_url(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode('utf-8', errors='replace')


def parse_overview_rows(html):
    """Parse v=111 overview table -> list of dicts with company info"""
    soup = BeautifulSoup(html, 'lxml')
    table = soup.find('table', class_='screener_table')
    if not table:
        return []
    stocks = []
    for row in table.find_all('tr')[1:]:  # skip header
        cells = row.find_all('td')
        if len(cells) < 11:
            continue
        try:
            rank = int(cells[0].get_text(strip=True))
            ticker = cells[1].get_text(strip=True)
            price_str = cells[8].get_text(strip=True)
            change_str = cells[9].get_text(strip=True).replace('%', '')
            vol_str = cells[10].get_text(strip=True).replace(',', '')
            price = float(price_str) if price_str and price_str != '-' else 0
            change = float(change_str) if change_str and change_str != '-' else 0
            volume = int(vol_str) if vol_str and vol_str != '-' else 0
            stocks.append({
                'rank': rank,
                'ticker': ticker,
                'company': cells[2].get_text(strip=True),
                'sector': cells[3].get_text(strip=True),
                'industry': cells[4].get_text(strip=True),
                'marketCap': cells[6].get_text(strip=True),
                'pe': cells[7].get_text(strip=True),
                'price': price,
                'change': change,
                'volume': volume,
            })
        except (ValueError, IndexError):
            continue
    return stocks


def parse_perf_rows(html):
    """Parse v=141 performance table -> dict of ticker -> perfWeek"""
    soup = BeautifulSoup(html, 'lxml')
    table = soup.find('table', class_='screener_table')
    if not table:
        return {}
    perf = {}
    for row in table.find_all('tr')[1:]:
        cells = row.find_all('td')
        if len(cells) < 18:
            continue
        try:
            ticker = cells[1].get_text(strip=True)
            perf_week_str = cells[2].get_text(strip=True).replace('%', '')
            perf_week = float(perf_week_str) if perf_week_str and perf_week_str != '-' else None
            perf[ticker] = {
                'perfWeek': perf_week,
                'perfWeekStr': cells[2].get_text(strip=True) if cells[2].get_text(strip=True) else '-',
            }
        except (ValueError, IndexError):
            continue
    return perf


def parse_breadth(html):
    soup = BeautifulSoup(html, 'lxml')
    for tag in soup.find_all(['td', 'span', 'div']):
        text = tag.get_text(strip=True)
        if 'Advancing' in text and 'Declining' in text:
            adv = re.search(r'Advancing([\d.]+)%\s*\((\d+)\)', text)
            dec = re.search(r'Declining\((\d+)\)\s*([\d.]+)%', text)
            nh = re.search(r'New High([\d.]+)%\s*\((\d+)\)', text)
            nl = re.search(r'New Low\((\d+)\)\s*([\d.]+)%', text)
            a50 = re.search(r'Above([\d.]+)%\s*\((\d+)\)SMA50', text)
            b50_all = list(re.finditer(r'Below\((\d+)\)\s*([\d.]+)%', text))
            a200 = re.search(r'Above([\d.]+)%\s*\((\d+)\)SMA200', text)

            if adv and dec:
                return {
                    'advancing': int(adv.group(2)),
                    'advancingPct': float(adv.group(1)),
                    'declining': int(dec.group(1)),
                    'decliningPct': float(dec.group(2)),
                    'newHigh': int(nh.group(2)) if nh else 0,
                    'newHighPct': float(nh.group(1)) if nh else 0,
                    'newLow': int(nl.group(1)) if nl else 0,
                    'newLowPct': float(nl.group(2)) if nl else 0,
                    'aboveSMA50': int(a50.group(2)) if a50 else 0,
                    'aboveSMA50Pct': float(a50.group(1)) if a50 else 0,
                    'belowSMA50': int(b50_all[0].group(1)) if b50_all else 0,
                    'belowSMA50Pct': float(b50_all[0].group(2)) if b50_all else 0,
                    'aboveSMA200': int(a200.group(2)) if a200 else 0,
                    'aboveSMA200Pct': float(a200.group(1)) if a200 else 0,
                    'belowSMA200': int(b50_all[1].group(1)) if len(b50_all) >= 2 else 0,
                    'belowSMA200Pct': float(b50_all[1].group(2)) if len(b50_all) >= 2 else 0,
                }
            break
    return {}


def parse_futures(html):
    soup = BeautifulSoup(html, 'lxml')
    futures = []
    seen = set()
    for link in soup.find_all('a', href=True):
        href = link.get('href', '')
        if 'futures_' in href:
            name = link.get_text(strip=True)
            if not name or name in seen:
                continue
            seen.add(name)
            parent = link.find_parent('tr')
            if parent:
                cells = parent.find_all('td')
                nums = []
                for c in cells:
                    t = c.get_text(strip=True)
                    if re.match(r'^[+-]?[\d,.]+%?$', t):
                        nums.append(t)
                if len(nums) >= 3:
                    try:
                        futures.append({
                            'name': name,
                            'last': float(nums[0].replace(',', '')),
                            'change': nums[1],
                            'changePct': float(nums[2].replace('%', '')),
                        })
                    except ValueError:
                        pass
    return futures


def parse_patterns(html):
    """Parse chart patterns from homepage - each pattern row has 4 tickers + pattern name"""
    soup = BeautifulSoup(html, 'lxml')
    patterns = []
    seen = set()

    # Map of raw pattern text -> (display name, direction)
    PATTERN_MAP = {
        'TrendlineTLSupp.': ('TL Support', 'bullish'),
        'Trendline TL Supp.': ('TL Support', 'bullish'),
        'TrendlineTLResist.': ('TL Resistance', 'bearish'),
        'Trendline TL Resist.': ('TL Resistance', 'bearish'),
        'Horizontal S/R': ('Horizontal S/R', 'neutral'),
        'Wedge Up': ('Wedge Up', 'bullish'),
        'Wedge': ('Wedge', 'neutral'),
        'Wedge Down': ('Wedge Down', 'bearish'),
        'TriangleAsc.Asc.': ('Triangle Ascending', 'bullish'),
        'Triangle Asc.': ('Triangle Ascending', 'bullish'),
        'TriangleDesc.Desc.': ('Triangle Descending', 'bearish'),
        'Triangle Desc.': ('Triangle Descending', 'bearish'),
        'Channel Up': ('Channel Up', 'bullish'),
        'Channel': ('Channel', 'neutral'),
        'Channel Down': ('Channel Down', 'bearish'),
        'Double Top': ('Double Top', 'bearish'),
        'Multiple Top': ('Multiple Top', 'bearish'),
        'Double Bottom': ('Double Bottom', 'bullish'),
        'Multiple Bottom': ('Multiple Bottom', 'bullish'),
        'Head&Shoulders': ('Head & Shoulders', 'bearish'),
        'Head & Shoulders': ('Head & Shoulders', 'bearish'),
        'H&S Inverse': ('H&S Inverse', 'bullish'),
    }

    all_pattern_keys = set(PATTERN_MAP.keys())

    for td in soup.find_all('td'):
        text = td.get_text(strip=True)
        if text in all_pattern_keys:
            display_name, direction = PATTERN_MAP[text]
            if display_name in seen:
                continue
            seen.add(display_name)
            # Count tickers in the same row
            parent_tr = td.find_parent('tr')
            if parent_tr:
                all_tds = parent_tr.find_all('td')
                tickers = [t.get_text(strip=True) for t in all_tds
                          if t.get_text(strip=True) != text
                          and t.get_text(strip=True)
                          and t.get_text(strip=True) not in all_pattern_keys]
                patterns.append({
                    'name': display_name,
                    'count': len(tickers),
                    'direction': direction,
                    'tickers': tickers[:4],
                })

    return patterns


def parse_headline(html):
    soup = BeautifulSoup(html, 'lxml')
    for link in soup.find_all('a', class_='nn-tab-link'):
        text = link.get_text(strip=True)
        if text and len(text) > 10:
            return text
    return 'Finviz Market Dashboard'


@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/api/data')
def get_data():
    try:
        urls = {
            'home': HOMEPAGE,
            'p1_111': SCREENER_111,
            'p2_111': SCREENER_111 + '&r=21',
            'p3_111': SCREENER_111 + '&r=41',
            'p1_141': SCREENER_141,
            'p2_141': SCREENER_141 + '&r=21',
            'p3_141': SCREENER_141 + '&r=41',
        }

        # Fetch all pages in parallel
        results = {}
        with ThreadPoolExecutor(max_workers=7) as executor:
            futures_map = {executor.submit(fetch_url, url): key for key, url in urls.items()}
            for future in futures_map:
                key = futures_map[future]
                try:
                    results[key] = future.result(timeout=25)
                except Exception as e:
                    results[key] = ''

        # Parse overview stocks from all pages
        all_stocks = []
        for key in ['p1_111', 'p2_111', 'p3_111']:
            if results.get(key):
                all_stocks.extend(parse_overview_rows(results[key]))

        # Parse performance data and merge
        perf_data = {}
        for key in ['p1_141', 'p2_141', 'p3_141']:
            if results.get(key):
                perf_data.update(parse_perf_rows(results[key]))

        # Merge perf week into stocks
        for stock in all_stocks:
            perf = perf_data.get(stock['ticker'], {})
            stock['perfWeek'] = perf.get('perfWeek')
            stock['perfWeekStr'] = perf.get('perfWeekStr', '-')

        # Filter: positive weekly performance only
        total_before = len(all_stocks)
        filtered = [s for s in all_stocks if s['perfWeek'] is not None and s['perfWeek'] > 0]
        filtered_out = total_before - len(filtered)

        # Re-rank and cap at 30
        for i, s in enumerate(filtered[:30]):
            s['rank'] = i + 1
        stocks = filtered[:30]

        # Parse homepage data
        home_html = results.get('home', '')
        breadth = parse_breadth(home_html) if home_html else {}
        futures_data = parse_futures(home_html) if home_html else []
        patterns = parse_patterns(home_html) if home_html else []
        headline = parse_headline(home_html) if home_html else ''

        from datetime import datetime
        now = datetime.now().strftime('%a, %b %d %Y %I:%M %p')

        return jsonify({
            'stocks': stocks,
            'breadth': breadth,
            'futures': futures_data,
            'patterns': patterns,
            'headline': headline,
            'lastUpdated': now,
            'totalBeforeFilter': total_before,
            'filteredOut': filtered_out,
        })
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500


if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
