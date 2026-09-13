import React from 'react';
import { CheckCircle2, AlertCircle } from 'lucide-react';

interface StatusBadgeProps {
  status: 'online' | 'offline' | 'loading';
  text?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, text }) => {
  if (status === 'online') {
    return (
      <span className="badge badge-success">
        <CheckCircle2 size={12} />
        {text || 'Бэкенд активен'}
      </span>
    );
  }

  return (
    <span className="badge badge-pending">
      <AlertCircle size={12} />
      {text || 'Ожидание подключения к бэкенду'}
    </span>
  );
};
