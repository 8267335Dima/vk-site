// --- frontend/src/pages/Scenarios/editor/nodes/ActionNode.js ---
import React, { useState } from 'react';
import { FormControl, Select, MenuItem } from '@mui/material';
import { NodeWrapper, InputHandle, OutputHandle } from './common';
import { content } from 'content/content';

const ActionNode = ({ data }) => {
    const [action, setAction] = useState(data.actionType || '');

    const handleSettingsClick = () => {
        // Открыть модальное окно с настройками для `action`
        console.log(`Settings for ${action}`);
    };

    return (
        <NodeWrapper title="Действие" onSettingsClick={action ? handleSettingsClick : null}>
            <InputHandle />
            <FormControl fullWidth size="small">
                <Select value={action} onChange={(e) => setAction(e.target.value)} displayEmpty>
                    <MenuItem value="" disabled><em>Выберите действие</em></MenuItem>
                    {Object.entries(content.actions).map(([key, { title }]) => (
                        <MenuItem key={key} value={key}>{title}</MenuItem>
                    ))}
                </Select>
            </FormControl>
            <OutputHandle id="next" />
        </NodeWrapper>
    );
};

export default ActionNode;