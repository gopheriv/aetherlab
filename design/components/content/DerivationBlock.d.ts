import React from 'react';

/**
 * @startingPoint section="Components" subtitle="Typeset equation + numbered steps + copy/export" viewport="700x320"
 */
export interface DerivationStep {
  text: string;
  equation?: string;
}

export interface DerivationBlockProps {
  summaryEquation: string;
  steps: DerivationStep[];
  keywords?: string[];
  onCopy?: () => void;
  onExport?: () => void;
}
