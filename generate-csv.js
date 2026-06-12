const { JSDOM } = require('jsdom');
const fs = require('fs');

const html = fs.readFileSync('index.html', 'utf8');
const { document } = new JSDOM(html).window;

const MONTHS = {Jan:'01',Fev:'02',Mar:'03',Abr:'04',Mai:'05',Jun:'06',
                Jul:'07',Ago:'08',Set:'09',Out:'10',Nov:'11',Dez:'12'};

const CONSECUTIVE_PAIRS = {'07:40':'08:00','09:40':'10:00','15:30':'15:50','20:40':'20:50'};

function extractCalendarRows() {
  const rows = [];
  document.querySelectorAll('#cal-container .cal-week').forEach(week => {
    const table = week.querySelector('table.cal-table');
    if (!table) return;
    const titleText = week.querySelector('.cal-titulo')?.textContent || '';
    const yearMatch = titleText.match(/\d{4}/);
    const year = yearMatch ? yearMatch[0] : '2026';
    const dayDates = [];
    table.querySelectorAll('thead th.cal-th-dia').forEach(th => {
      const m = th.textContent.trim().match(/(\d{1,2})\/(\w{3})/);
      if (m) {
        const day = m[1].padStart(2, '0');
        const mon = MONTHS[m[2].slice(0, 3)] || '??';
        dayDates.push(day + '/' + mon + '/' + year);
      } else {
        dayDates.push('');
      }
    });
    table.querySelectorAll('tbody tr').forEach(tr => {
      const horTd = tr.querySelector('td.cal-td-hor');
      if (!horTd) return;
      const parts = horTd.textContent.trim().split(/[–\-]/);
      const horaInicio = (parts[0] || '').trim();
      const horaFim = (parts[1] || '').trim();
      tr.querySelectorAll('td.cal-td').forEach((td, i) => {
        const data = dayDates[i] || '';
        td.querySelectorAll('.cal-entry').forEach(entry => {
          const codSpan = entry.querySelector('.cal-cod');
          const turmaFull = (entry.querySelector('.cal-turma')?.textContent || '').trim();
          const dashIdx = turmaFull.indexOf('-');
          const cargo = dashIdx >= 0 ? turmaFull.slice(0, dashIdx) : turmaFull;
          const turma = dashIdx >= 0 ? turmaFull.slice(dashIdx + 1) : turmaFull;
          let codigo = '';
          if (codSpan) {
            const cl = codSpan.cloneNode(true);
            cl.querySelectorAll('span').forEach(s => s.remove());
            codigo = cl.textContent.trim().replace(/\.(\d)(?!\d)/, '.0$1');
          }
          rows.push({ cargo, codigo, turma, data, horaInicio, horaFim });
        });
      });
    });
  });
  return rows;
}

function mergeConsecutiveRows(data) {
  const groups = {};
  data.forEach(r => {
    const key = r.cargo + '|' + r.codigo + '|' + r.turma + '|' + r.data;
    if (!groups[key]) groups[key] = [];
    groups[key].push(r);
  });
  const merged = [];
  Object.values(groups).forEach(group => {
    group.sort((a, b) => a.horaInicio.localeCompare(b.horaInicio));
    let i = 0;
    while (i < group.length) {
      const cur = group[i];
      const next = group[i + 1];
      const afterNext = group[i + 2];
      const consNext = next && CONSECUTIVE_PAIRS[cur.horaFim] === next.horaInicio;
      const consAfter = afterNext && next && CONSECUTIVE_PAIRS[next.horaFim] === afterNext.horaInicio;
      if (consNext && consAfter) {
        merged.push(cur, next, afterNext);
        i += 3;
      } else if (consNext) {
        merged.push({ ...cur, horaFim: next.horaFim });
        i += 2;
      } else {
        merged.push(cur);
        i++;
      }
    }
  });
  return merged;
}

const data = mergeConsecutiveRows(extractCalendarRows());
const rows = [
  ['cargo', 'codigo', 'turma', 'data', 'horaInicio', 'horaFim'],
  ...data.map(r => [r.cargo, r.codigo, r.turma, r.data, r.horaInicio, r.horaFim])
];
const csv = rows.map(r => r.map(v => '"' + String(v).replace(/"/g, '""') + '"').join(';')).join('\r\n');
fs.writeFileSync('calendario.csv', '﻿' + csv, 'utf8');
console.log(`CSV gerado: ${data.length} registros -> calendario.csv`);
