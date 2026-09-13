import React from 'react';
import { Upload, FileText } from 'lucide-react';

interface FileUploadCardProps {
  title: string;
  description: string;
  acceptedFormats: string;
  fileTypeLabel: string;
  icon?: React.ReactNode;
}

export const FileUploadCard: React.FC<FileUploadCardProps> = ({
  title,
  description,
  acceptedFormats,
  fileTypeLabel,
  icon,
}) => {
  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          <div style={{ background: '#f1f5f9', color: '#0f172a', padding: '0.5rem', borderRadius: '0.5rem' }}>
            {icon || <FileText size={24} />}
          </div>
          <div>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 600 }}>{title}</h3>
            <span style={{ fontSize: '0.75rem', color: '#64748b' }}>{fileTypeLabel}</span>
          </div>
        </div>
      </div>

      <p style={{ fontSize: '0.875rem', color: '#475569', minHeight: '2.5rem' }}>
        {description}
      </p>

      <div
        style={{
          border: '2px dashed #cbd5e1',
          borderRadius: '0.5rem',
          padding: '1.5rem',
          textAlign: 'center',
          background: '#f8fafc',
          cursor: 'pointer',
          transition: 'border-color 0.2s',
        }}
      >
        <Upload size={24} color="#94a3b8" style={{ marginBottom: '0.5rem' }} />
        <p style={{ fontSize: '0.875rem', fontWeight: 500, color: '#334155' }}>
          Перетащите файл или нажмите для выбора
        </p>
        <p style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '0.25rem' }}>
          Поддерживаемые форматы: {acceptedFormats}
        </p>
      </div>
    </div>
  );
};
