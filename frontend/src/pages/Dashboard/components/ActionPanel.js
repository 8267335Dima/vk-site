// frontend/src/pages/Dashboard/components/ActionPanel.js
import React from 'react';
import { Typography, Button, List, ListItem, ListItemText, ListItemIcon, Stack, Paper, alpha } from '@mui/material';
// ИСПРАВЛЕНО
import { content } from '../../../content/content';
import { motion } from 'framer-motion';

export default function ActionPanel({ onConfigure }) {
  return (
    <Paper sx={{ p: 3, height: '100%' }}>
      <Typography variant="h6" gutterBottom sx={{ fontWeight: 600, mb: 2 }}>
        Панель действий
      </Typography>
      <List sx={{ p: 0 }}>
        <Stack spacing={1.5}>
          {Object.entries(content.tasks).map(([key, action]) => ( // ИСПРАВЛЕНО: content.actions -> content.tasks
            <motion.div whileHover={{ scale: 1.03 }} transition={{ type: 'spring', stiffness: 400, damping: 10 }} key={key}>
                <ListItem
                  secondaryAction={
                    <Button edge="end" variant="contained" size="small" onClick={() => onConfigure(key, action.modalTitle)}>
                      Настроить
                    </Button>
                  }
                  sx={{
                    p: 2, borderRadius: 3,
                    bgcolor: 'background.default',
                    border: '1px solid', borderColor: 'divider',
                    display: 'flex', alignItems: 'center', gap: 2,
                    cursor: 'pointer',
                    '&:hover': {
                        borderColor: 'primary.main',
                        boxShadow: (theme) => `0 4px 16px ${alpha(theme.palette.primary.main, 0.2)}`,
                    },
                  }}
                  onClick={() => onConfigure(key, action.modalTitle)}
                >
                  <ListItemIcon sx={{ color: 'primary.main', minWidth: 'auto', mr: 0, fontSize: '2rem' }}>
                    {action.icon}
                  </ListItemIcon>
                  <ListItemText
                    primary={action.name} // ИСПРАВЛЕНО: action.title -> action.name
                    sx={{
                      '& .MuiListItemText-primary': { fontWeight: 600 },
                      m: 0,
                    }}
                  />
                </ListItem>
            </motion.div>
          ))}
        </Stack>
      </List>
    </Paper>
  );
}