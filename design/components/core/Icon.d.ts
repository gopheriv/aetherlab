import React from 'react';

export interface IconProps {
  /** Lucide icon name, e.g. "play", "settings", "x" — see lucide.dev/icons */
  name: string;
  size?: number;
  strokeWidth?: number;
  color?: string;
  style?: React.CSSProperties;
}
