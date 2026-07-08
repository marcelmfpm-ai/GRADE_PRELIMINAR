"""
Regenera o bloco DADOS_AULAS embutido em disponibilidade-professor.html
a partir do calendário vivo em index.html (#cal-container .cal-week).

Uso: python3 generate-professor-data.py
(depende de beautifulsoup4: pip install beautifulsoup4)

Mantém a mesma lógica de extração/merge de extractCalendarRows +
mergeConsecutiveRows do index.html/generate-csv.js, mas preserva a
descrição da aula (que o calendario.csv não guarda) e não faz o
zero-padding do código do módulo (mantém "M2.1", não "M2.01").
"""
import re
import json
from copy import deepcopy
from bs4 import BeautifulSoup

INDEX_HTML = 'index.html'
TARGET_HTML = 'disponibilidade-professor.html'

MONTHS = {'Jan': '01', 'Fev': '02', 'Mar': '03', 'Abr': '04', 'Mai': '05', 'Jun': '06',
          'Jul': '07', 'Ago': '08', 'Set': '09', 'Out': '10', 'Nov': '11', 'Dez': '12'}
CONSECUTIVE_PAIRS = {'07:40': '08:00', '09:40': '10:00', '15:30': '15:50', '20:40': '20:50'}


def extract_calendar_rows(soup):
    rows = []
    for week in soup.select('#cal-container .cal-week'):
        table = week.select_one('table.cal-table')
        if not table:
            continue
        titulo = week.select_one('.cal-titulo')
        title_text = titulo.get_text() if titulo else ''
        ym = re.search(r'\d{4}', title_text)
        year = ym.group(0) if ym else '2026'

        day_dates = []
        for th in table.select('thead th.cal-th-dia'):
            m = re.search(r'(\d{1,2})/(\w{3})', th.get_text().strip())
            if m:
                day = m.group(1).zfill(2)
                mon = MONTHS.get(m.group(2)[:3], '??')
                day_dates.append(f"{day}/{mon}/{year}")
            else:
                day_dates.append('')

        for tr in table.select('tbody tr'):
            hor_td = tr.select_one('td.cal-td-hor')
            if not hor_td:
                continue
            parts = re.split(r'[–\-]', hor_td.get_text().strip())
            hora_inicio = (parts[0] if len(parts) > 0 else '').strip()
            hora_fim = (parts[1] if len(parts) > 1 else '').strip()

            tds = [td for td in tr.find_all('td', recursive=False) if 'cal-td' in td.get('class', [])]
            for i, td in enumerate(tds):
                data = day_dates[i] if i < len(day_dates) else ''
                for entry in td.select('.cal-entry'):
                    cod_span = entry.select_one('.cal-cod')
                    turma_el = entry.select_one('.cal-turma')
                    desc_el = entry.select_one('.cal-desc')
                    turma_full = turma_el.get_text().strip() if turma_el else ''
                    dash_idx = turma_full.find('-')
                    cargo = turma_full[:dash_idx] if dash_idx >= 0 else turma_full
                    turma = turma_full[dash_idx + 1:] if dash_idx >= 0 else turma_full

                    codigo = ''
                    if cod_span:
                        cl = deepcopy(cod_span)
                        for s in cl.find_all('span'):
                            s.decompose()
                        codigo = cl.get_text().strip()

                    descricao = desc_el.get_text().strip() if desc_el else ''

                    rows.append({
                        'cargo': cargo, 'codigo': codigo, 'descricao': descricao,
                        'turma': turma, 'data': data, 'horaInicio': hora_inicio, 'horaFim': hora_fim
                    })
    return rows


def merge_consecutive_rows(data):
    groups = {}
    for r in data:
        key = f"{r['cargo']}|{r['codigo']}|{r['descricao']}|{r['turma']}|{r['data']}"
        groups.setdefault(key, []).append(r)

    merged = []
    for group in groups.values():
        group.sort(key=lambda r: r['horaInicio'])
        i, n = 0, len(group)
        while i < n:
            cur = group[i]
            nxt = group[i + 1] if i + 1 < n else None
            after = group[i + 2] if i + 2 < n else None
            cons_next = nxt is not None and CONSECUTIVE_PAIRS.get(cur['horaFim']) == nxt['horaInicio']
            cons_after = after is not None and nxt is not None and CONSECUTIVE_PAIRS.get(nxt['horaFim']) == after['horaInicio']
            if cons_next and cons_after:
                merged += [cur, nxt, after]
                i += 3
            elif cons_next:
                m = dict(cur)
                m['horaFim'] = nxt['horaFim']
                merged.append(m)
                i += 2
            else:
                merged.append(cur)
                i += 1
    return merged


def main():
    with open(INDEX_HTML, encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')

    data = merge_consecutive_rows(extract_calendar_rows(soup))
    data.sort(key=lambda r: ('-'.join(reversed(r['data'].split('/'))), r['horaInicio']))

    js_array = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    js_array = js_array.replace('</script', '<\\/script')

    with open(TARGET_HTML, encoding='utf-8') as f:
        html = f.read()

    pattern = re.compile(
        r'(/\* BEGIN_DADOS_AULAS.*?\*/\s*const DADOS_AULAS = )(\[.*?\])(;\s*/\* END_DADOS_AULAS \*/)',
        re.S
    )
    new_html, count = pattern.subn(lambda m: m.group(1) + js_array + m.group(3), html)
    if count != 1:
        raise SystemExit(f"Marcador BEGIN_DADOS_AULAS/END_DADOS_AULAS não encontrado corretamente em {TARGET_HTML} (count={count})")

    with open(TARGET_HTML, 'w', encoding='utf-8') as f:
        f.write(new_html)

    print(f"OK: {len(data)} registros gravados em {TARGET_HTML}")


if __name__ == '__main__':
    main()
