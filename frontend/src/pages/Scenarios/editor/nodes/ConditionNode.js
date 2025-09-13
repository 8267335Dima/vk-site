import React, { useState } from 'react';
import {
  FormControl,
  Select,
  MenuItem,
  Stack,
  Typography,
  TextField,
} from '@mui/material';
import { Handle, Position } from 'reactflow';
import { NodeWrapper, InputHandle } from './common';

const availableConditions = [
  {
    key: 'friends_count',
    label: 'Количество друзей',
    type: 'number',
    operators: ['>', '<', '=='],
  },
  {
    key: 'day_of_week',
    label: 'День недели',
    type: 'select',
    operators: ['=='],
    options: [{ value: '1', label: 'Пн' }],
  },
];

const ConditionNode = () => {
  const [condition, setCondition] = useState('');
  const selectedCondition = availableConditions.find(
    (c) => c.key === condition
  );

  return (
    <NodeWrapper title="Условие">
      <InputHandle />
      <Stack spacing={2}>
        <FormControl fullWidth size="small">
          <Select
            value={condition}
            onChange={(e) => setCondition(e.target.value)}
            displayEmpty
          >
            <MenuItem value="" disabled>
              <em>Выберите метрику</em>
            </MenuItem>
            {availableConditions.map((c) => (
              <MenuItem key={c.key} value={c.key}>
                {c.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        {selectedCondition && (
          <Stack direction="row" spacing={1} alignItems="center">
            <FormControl sx={{ minWidth: 80 }} size="small">
              <Select defaultValue=">">
                {selectedCondition.operators.map((op) => (
                  <MenuItem key={op} value={op}>
                    {op}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField size="small" type={selectedCondition.type} />
          </Stack>
        )}
      </Stack>
      <Handle
        type="source"
        position={Position.Right}
        id="on_success"
        style={{ top: '35%', background: '#4CAF50' }}
      />
      <Typography
        variant="caption"
        sx={{
          position: 'absolute',
          right: -25,
          top: '35%',
          transform: 'translateY(-50%)',
          color: '#4CAF50',
        }}
      >
        Да
      </Typography>
      <Handle
        type="source"
        position={Position.Right}
        id="on_failure"
        style={{ top: '65%', background: '#F44336' }}
      />
      <Typography
        variant="caption"
        sx={{
          position: 'absolute',
          right: -25,
          top: '65%',
          transform: 'translateY(-50%)',
          color: '#F44336',
        }}
      >
        Нет
      </Typography>
    </NodeWrapper>
  );
};

export default ConditionNode;
