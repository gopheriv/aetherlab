import React from 'react';

export interface CommandBarProps {
  value: string;
  onChange?: (v: string) => void;
  placeholder?: string;
  busy?: boolean;
  quality?: 'draft' | 'standard' | 'high';
  onQualityChange?: (q: string) => void;
  examples?: string[];
  onRun?: () => void;
  onCancel?: () => void;
}
