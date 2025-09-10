// frontend/src/pages/Dashboard/components/ActionPanel.js
import React from 'react';
import { Typography, Button, List, ListItem, ListItemText, ListItemIcon, Stack, Paper } from '@mui/material';
import { dashboardContent } from 'content/dashboardContent';

export default function ActionPanel({ onConfigure }) {
  const { title, actions } = dashboardContent.actionPanel;

  return (
    // --- ИЗМЕНЕНИЕ: Обертка в Paper для единого стиля ---
    <Paper sx={{ p: 3, height: '100%' }}>
      <Typography variant="h5" gutterBottom sx={{ fontWeight: 600, mb: 2 }}>
        {title}
      </Typography>
      <List sx={{ p: 0 }}>
        <Stack spacing={1.5}>
          {actions.map((action) => (
            <ListItem
              key={action.key}
              secondaryAction={
                <Button edge="end" variant="contained" size="small" onClick={() => onConfigure(action.key, action.title)}>
                  {dashboardContent.tasks.launchButton}
                </Button>
              }
              sx={{
                p: 2,
                borderRadius: 3,
                border: '1px solid',
                borderColor: 'divider',
                bgcolor: 'action.hover', // --- ИЗМЕНЕНИЕ: Небольшой фон для контраста
                display: 'flex',
                alignItems: 'center',
                gap: 2,
                transition: 'transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out',
                '&:hover': {
                  transform: 'translateY(-2px) scale(1.02)',
                  boxShadow: (theme) => `0 8px 24px -8px ${theme.palette.primary.main}33`,
                  borderColor: 'primary.main',
                },
              }}
            >
              <ListItemIcon sx={{ color: 'primary.main', minWidth: 'auto', mr: 0, fontSize: '2rem' }}>
                {action.icon}
              </ListItemIcon>
              <ListItemText
                primary={action.title}
                // --- ИЗМЕНЕНИЕ: Убрал описание для компактности, оно есть в тултипе ---
                sx={{
                  '& .MuiListItemText-primary': { fontWeight: 600 },
                  m: 0,
                  flexGrow: 1,
                  // --- ИЗМЕНЕНИЕ: Предотвращение "наезда" кнопки на текст ---
                  maxWidth: 'calc(100% - 130px)', 
                }}
              />
            </ListItem>
          ))}
        </Stack>
      </List>
    </Paper>
  );
}