import React from 'react';

export interface ToastProps {
  kind?: 'error' | 'warning' | 'info' | 'success';
  message: string;
  detail?: string;
  onDismiss?: () => void;
  onDetails?: () => void;
}
