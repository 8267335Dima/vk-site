// --- frontend/src/pages/Scenarios/editor/Sidebar.js ---
import React from 'react';
import { Paper, Typography, Box } from '@mui/material';

const DraggableNode = ({ type, label }) => {
    const onDragStart = (event, nodeType) => {
        event.dataTransfer.setData('application/reactflow', nodeType);
        event.dataTransfer.effectAllowed = 'move';
    };

    return (
        <Box
            onDragStart={(event) => onDragStart(event, type)}
            draggable
            sx={{
                p: 1.5,
                border: 1,
                borderColor: 'divider',
                borderRadius: 2,
                bgcolor: 'background.paper',
                cursor: 'grab',
                '&:hover': {
                    borderColor: 'primary.main',
                    boxShadow: 3,
                }
            }}
        >
            <Typography variant="body2" sx={{ fontWeight: 500 }}>{label}</Typography>
        </Box>
    );
};

const Sidebar = () => {
    return (
        <Paper sx={{ width: 250, p: 2, m: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
            <Typography variant="h6">Инструменты</Typography>
            <DraggableNode type="action" label="Действие" />
            <DraggableNode type="condition" label="Условие" />
        </Paper>
    );
};

export default Sidebar;