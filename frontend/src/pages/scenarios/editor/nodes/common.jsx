import React from 'react';
import { Handle, Position } from 'reactflow';
import { Paper, Typography, Box, IconButton, Tooltip } from '@mui/material';
import SettingsIcon from '@mui/icons-material/Settings';

export const NodeWrapper = ({ children, title, onSettingsClick }) => (
  <Paper
    sx={{ border: 2, borderColor: 'primary.main', borderRadius: 2, width: 250 }}
  >
    <Box
      sx={{
        p: 1,
        bgcolor: 'primary.main',
        color: 'primary.contrastText',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
      }}
    >
      <Typography variant="body2" sx={{ fontWeight: 600 }}>
        {title}
      </Typography>
      {onSettingsClick && (
        <Tooltip title="Настройки шага">
          <IconButton
            size="small"
            onClick={onSettingsClick}
            sx={{ color: 'primary.contrastText' }}
          >
            <SettingsIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      )}
    </Box>
    <Box sx={{ p: 2 }}>{children}</Box>
  </Paper>
);

export const InputHandle = () => (
  <Handle
    type="target"
    position={Position.Left}
    style={{ background: '#555' }}
  />
);
export const OutputHandle = ({ id }) => (
  <Handle
    type="source"
    position={Position.Right}
    id={id}
    style={{ background: '#555' }}
  />
);
