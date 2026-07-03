import React from 'react';

export interface ParameterRowProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  unit?: string;
  defaultValue?: number;
  onChange?: (v: number) => void;
}
