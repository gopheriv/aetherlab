import React from 'react';

export interface ReferenceCardProps {
  source: string;
  page?: string;
  score?: number;
  excerpt: string;
  onOpen?: () => void;
}
