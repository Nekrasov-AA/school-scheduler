import React from 'react';
import { Calendar, Cpu, Sparkles } from 'lucide-react';

export const Header: React.FC = () => {
  return (
    <header style={{ borderBottom: '1px solid #e2e8f0', background: '#ffffff', padding: '1rem 0' }}>
      <div className="container" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0 1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div style={{ background: '#eff6ff', color: '#2563eb', padding: '0.5rem', borderRadius: '0.5rem', display: 'flex' }}>
            <Calendar size={28} />
          </div>
          <div>
            <h1 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#0f172a' }}>
              School Scheduler
            </h1>
            <p style={{ fontSize: '0.85rem', color: '#64748b' }}>
              Автоматическое составление школьного расписания (OR-Tools)
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.875rem', color: '#475569' }}>
            <Cpu size={16} color="#2563eb" />
            CP-SAT Solver
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.875rem', color: '#16a34a' }}>
            <Sparkles size={16} />
            SanPiN Compliant
          </span>
        </div>
      </div>
    </header>
  );
};
