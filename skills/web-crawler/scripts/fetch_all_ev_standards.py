#!/usr/bin/env python3
import re
import time
import urllib.parse
from fetch import fetch_html, fetch_rendered_html, is_empty_shell
from parse import parse_html

def extract_standards_from_content(content):
    lines = content.split('\n')
    standards = []
    for line in lines:
        if '|' in line and ('GB ' in line or 'GB/T' in line or 'GB/Z' in line):
            parts = line.split('|')
            parts = [p.strip() for p in parts]
            if len(parts) >= 10:
                try:
                    no = parts[1]
                    std_link = parts[2]
                    name_link = parts[4]
                    std_type = parts[5]
                    status = parts[6]
                    pub_date = parts[7]

                    std_match = re.search(r'\[(GB[^\]]+)\]', std_link)
                    if std_match:
                        std_num = std_match.group(1)
                    else:
                        continue

                    name_match = re.search(r'\[([^\]]+)\]', name_link)
                    if name_match:
                        name = name_match.group(1)
                    else:
                        continue

                    if no.isdigit():
                        standards.append({
                            'no': int(no),
                            'standard': std_num,
                            'name': name,
                            'type': std_type,
                            'status': status,
                            'pub_date': pub_date
                        })
                except:
                    pass
    return standards

def main():
    all_standards = []
    keyword = '电动汽车'
    encoded = urllib.parse.quote(keyword)

    for page in range(1, 20):
        url = f'https://openstd.samr.gov.cn/bzgk/gb/std_list?p.p1=0&p.p90=circulation_date&p.p91=desc&p.p2={encoded}&p.p3=10&p.p4={page}'
        print(f'Fetching page {page}...')

        result = fetch_html(url)
        if result['status'] != 'failed' and result.get('content'):
            html = result['content'].decode('utf-8', errors='ignore')
            if is_empty_shell(html):
                result = fetch_rendered_html(url)
                if result['status'] != 'failed':
                    html = result['content'].decode('utf-8', errors='ignore') if isinstance(result['content'], bytes) else result['content']

            parsed = parse_html(html, base_url=url)
            standards = extract_standards_from_content(parsed['markdown'])
            all_standards.extend(standards)
            print(f'  -> Found {len(standards)} standards (total: {len(all_standards)})')
        else:
            print(f'  -> Failed')

        time.sleep(0.5)

    print(f'\n=== Total: {len(all_standards)} standards ===')

    # Save to file
    output_path = '/Users/siahu/Documents/TUV/workspace/skils_output/web-crawler/crawl_20260313_144817/files/all_ev_standards.txt'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('=== GB STANDARDS FOR ELECTRIC VEHICLE CERTIFICATION ===\n')
        f.write(f'Total: {len(all_standards)} standards\n')
        f.write(f'Search keyword: 电动汽车 (Electric Vehicle)\n')
        f.write(f'Source: https://openstd.samr.gov.cn\n\n')

        mandatory = [s for s in all_standards if '强标' in s['type']]
        recommended = [s for s in all_standards if '推标' in s['type']]

        f.write(f'=== MANDATORY STANDARDS - {len(mandatory)} ===\n\n')
        for s in mandatory:
            f.write(f"{s['standard']}\n")
            f.write(f"  Name: {s['name']}\n")
            f.write(f"  Status: {s['status']}\n")
            f.write(f"  Published: {s['pub_date']}\n\n")

        f.write(f'\n=== RECOMMENDED STANDARDS - {len(recommended)} ===\n\n')
        for s in recommended:
            f.write(f"{s['standard']}\n")
            f.write(f"  Name: {s['name']}\n")
            f.write(f"  Status: {s['status']}\n")
            f.write(f"  Published: {s['pub_date']}\n\n")

    print(f'Saved to: {output_path}')

if __name__ == '__main__':
    main()
