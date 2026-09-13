import React from 'react';
import { CalendarDays } from 'lucide-react';

const DAYS = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница'];
const PERIODS = [1, 2, 3, 4, 5, 6, 7];

export const ScheduleGrid: React.FC = () => {
  return (
    <div className="card" style={{ marginTop: '2rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <CalendarDays size={20} color="#2563eb" />
          <h3 style={{ fontSize: '1.1rem', fontWeight: 600 }}>Сетка расписания</h3>
        </div>
        <span style={{ fontSize: '0.875rem', color: '#64748b' }}>Режим предварительного просмотра</span>
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.875rem' }}>
          <thead>
            <tr style={{ background: '#f8fafc', borderBottom: '2px solid #e2e8f0' }}>
              <th style={{ padding: '0.75rem', color: '#475569', fontWeight: 600 }}>Урок</th>
              {DAYS.map((day) => (
                <th key={day} style={{ padding: '0.75rem', color: '#475569', fontWeight: 600 }}>
                  {day}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {PERIODS.map((period) => (
              <tr key={period} style={{ borderBottom: '1px solid #f1f5f9' }}>
                <td style={{ padding: '0.75rem', fontWeight: 600, color: '#64748b', background: '#fcfcfd' }}>
                  {period}
                </td>
                {DAYS.map((day) => (
                  <td key={`${day}-${period}`} style={{ padding: '0.75rem', color: '#94a3b8' }}>
                    <div
                      style={{
                        padding: '0.5rem',
                        borderRadius: '0.375rem',
                        background: '#f8fafc',
                        border: '1px dashed #e2e8f0',
                        textAlign: 'center',
                        fontSize: '0.75rem',
                      }}
                    >
                      —
                    </div>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
