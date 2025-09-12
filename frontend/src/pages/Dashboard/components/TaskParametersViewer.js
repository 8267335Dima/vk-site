// frontend/src/pages/Dashboard/components/TaskParametersViewer.js
import React from 'react';
import { Box, Typography, List, ListItem, ListItemIcon, ListItemText, Divider } from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import FilterListIcon from '@mui/icons-material/FilterList';

const sexMap = { 1: "Женский", 2: "Мужской" };

const ParameterItem = ({ icon, primary, secondary }) => (
    <ListItem sx={{ py: 0.5, px: 1 }}>
        <ListItemIcon sx={{ minWidth: 32, color: 'text.secondary' }}>{icon}</ListItemIcon>
        <ListItemText 
            primary={<Typography variant="body2">{primary}</Typography>} 
            secondary={secondary ? <Typography variant="caption">{secondary}</Typography> : null} 
        />
    </ListItem>
);

const TaskParametersViewer = ({ parameters }) => {
    if (!parameters || Object.keys(parameters).length === 0) {
        return <Typography variant="caption" color="text.secondary">Без дополнительных параметров.</Typography>;
    }

    const { count, filters, message_text, like_config, send_message_on_add } = parameters;
    const hasFilters = filters && Object.values(filters).some(val => val);

    return (
        <Box>
            <List dense>
                {count && <ParameterItem icon={<CheckCircleOutlineIcon fontSize="small"/>} primary={`Количество: ${count}`} />}
                
                {send_message_on_add && <ParameterItem icon={<CheckCircleOutlineIcon fontSize="small"/>} primary="Приветственное сообщение" />}
                
                {like_config?.enabled && <ParameterItem icon={<CheckCircleOutlineIcon fontSize="small"/>} primary="Лайк после заявки" />}

                {message_text && <ParameterItem icon={<CheckCircleOutlineIcon fontSize="small"/>} primary={`Текст: "${message_text}"`} />}

                {hasFilters && (
                    <>
                        <Divider sx={{ my: 1, mx: -2 }} />
                        <Typography variant="subtitle2" sx={{ fontWeight: 600, px: 1, mb: 0.5 }}>Фильтры:</Typography>
                        {filters.is_online && <ParameterItem icon={<FilterListIcon fontSize="small"/>} primary="Только онлайн" />}
                        {filters.sex && <ParameterItem icon={<FilterListIcon fontSize="small"/>} primary={`Пол: ${sexMap[filters.sex]}`} />}
                        {filters.allow_closed_profiles && <ParameterItem icon={<FilterListIcon fontSize="small"/>} primary="Включая закрытые профили" />}
                        {filters.status_keyword && <ParameterItem icon={<FilterListIcon fontSize="small"/>} primary={`Статус содержит: "${filters.status_keyword}"`} />}
                        {filters.min_friends && <ParameterItem icon={<FilterListIcon fontSize="small"/>} primary={`Друзей: от ${filters.min_friends}`} />}
                        {filters.max_friends && <ParameterItem icon={<FilterListIcon fontSize="small"/>} primary={`Друзей: до ${filters.max_friends}`} />}
                        {filters.min_followers && <ParameterItem icon={<FilterListIcon fontSize="small"/>} primary={`Подписчиков: от ${filters.min_followers}`} />}
                        {filters.max_followers && <ParameterItem icon={<FilterListIcon fontSize="small"/>} primary={`Подписчиков: до ${filters.max_followers}`} />}
                        {filters.last_seen_days && <ParameterItem icon={<FilterListIcon fontSize="small"/>} primary={`Не заходили более: ${filters.last_seen_days} дней`} />}
                    </>
                )}
            </List>
        </Box>
    );
};

export default TaskParametersViewer;