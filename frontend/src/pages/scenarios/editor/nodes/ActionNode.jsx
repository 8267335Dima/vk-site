import React, { useState } from 'react';
import { FormControl, Select, MenuItem } from '@mui/material';
import { NodeWrapper, InputHandle, OutputHandle } from './common';
import { content } from '@/shared/config/content';

const ActionNode = ({ data }) => {
  const [action, setAction] = useState(data.actionType || '');

  const handleSettingsClick = () => {
    console.log(`Settings for ${action}`);
  };

  return (
    <NodeWrapper
      title="Действие"
      onSettingsClick={action ? handleSettingsClick : null}
    >
      <InputHandle />
      <FormControl fullWidth size="small">
        <Select
          value={action}
          onChange={(e) => setAction(e.target.value)}
          displayEmpty
        >
          <MenuItem value="" disabled>
            <em>Выберите действие</em>
          </MenuItem>
          {Object.entries(content.actions).map(([key, { name }]) => (
            <MenuItem key={key} value={key}>
              {name}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
      <OutputHandle id="next" />
    </NodeWrapper>
  );
};

export default ActionNode;
