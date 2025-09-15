import React from 'react';
import { NodeWrapper, OutputHandle } from './common';

const StartNode = () => {
  return (
    <NodeWrapper title="Старт">
      <OutputHandle id="next" />
    </NodeWrapper>
  );
};

export default StartNode;
