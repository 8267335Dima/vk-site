// --- frontend/src/pages/Scenarios/editor/nodes/StartNode.js ---
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