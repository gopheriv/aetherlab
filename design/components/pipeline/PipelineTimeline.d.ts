import React from 'react';

export interface PipelineStage {
  label: string;
  status: 'pending' | 'active' | 'complete' | 'error';
  elapsed?: string;
}

export interface PipelineTimelineProps {
  stages: PipelineStage[];
  onCancel?: () => void;
}
