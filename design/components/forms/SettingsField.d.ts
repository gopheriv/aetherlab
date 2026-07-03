import React from 'react';

export interface SettingsFieldProps {
  label: string;
  kind?: 'text' | 'select' | 'path' | 'secret';
  value: string;
  options?: string[];
  placeholder?: string;
  hint?: string;
  onChange?: (v: string) => void;
  onBrowse?: () => void;
}
