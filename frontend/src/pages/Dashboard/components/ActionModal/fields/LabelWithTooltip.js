// frontend/src/pages/Dashboard/components/ActionModal/fields/LabelWithTooltip.js
import React from 'react';
// ИСПРАВЛЕНИЕ: Добавлен IconButton в импорт
import { Box, Tooltip, Typography, IconButton } from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';

export const LabelWithTooltip = ({ title, tooltipText, ...props }) => {
    return (
        <Box 
            display="flex" 
            alignItems="center" 
            component="span" 
            {...props}
        >
            <Typography 
                variant="body1"
                component="span" 
                sx={{ lineHeight: 1 }}
            >
                {title}
            </Typography>
            <Tooltip title={tooltipText} placement="top" arrow>
                {/* IconButton делает иконку кликабельной и улучшает a11y (доступность) */}
                <IconButton 
                    size="small" 
                    sx={{ 
                        ml: 0.5, 
                        p: 0.25, 
                        color: 'secondary.main', 
                        cursor: 'help' 
                    }}
                    aria-label={tooltipText} // Для скринридеров
                >
                    <InfoOutlinedIcon fontSize="small" />
                </IconButton>
            </Tooltip>
        </Box>
    );
};