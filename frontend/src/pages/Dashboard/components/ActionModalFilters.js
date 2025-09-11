// frontend/src/pages/Dashboard/components/ActionModalFilters.js
import React from 'react';
import {
    FormControlLabel, Switch, Select, MenuItem, InputLabel, FormControl, Grid, Typography, Box, Tooltip
} from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { content } from 'content/content';

const FilterWrapper = ({ children }) => (
    <Box>
        <Typography variant="subtitle1" sx={{ mb: 2, fontWeight: 600 }}>{content.modal.filtersTitle}</Typography>
        {children}
    </Box>
);

const LabelWithTooltip = ({ title, tooltipText }) => (
    <Box display="flex" alignItems="center" component="span">
        {title}
        <Tooltip title={tooltipText} placement="top" arrow>
            <InfoOutlinedIcon fontSize="small" color="secondary" sx={{ ml: 0.5, cursor: 'help' }} />
        </Tooltip>
    </Box>
);

// --- ИЗМЕНЕНИЕ: Добавлен export для использования в других модулях ---
export const CommonFiltersSettings = ({ filters, onChange, actionKey }) => {
    const showClosedProfilesFilter = ['accept_friends', 'add_recommended', 'mass_messaging'].includes(actionKey);
    const isAcceptFriends = actionKey === 'accept_friends';

    const handleChange = (e) => {
        const { name, value, type, checked } = e.target;
        const val = type === 'checkbox' ? checked : value;
        // Передаем чистое имя поля, родительский компонент сам обработает вложенность
        onChange(name, val);
    };

    return (
        <FilterWrapper>
            <Grid container spacing={2} alignItems="center">
                <Grid item xs={12} sm={6}>
                    <FormControlLabel control={<Switch name="is_online" checked={filters.is_online || false} onChange={handleChange} />} label="Только онлайн" />
                </Grid>
                {showClosedProfilesFilter && (
                    <Grid item xs={12} sm={6}>
                        <FormControlLabel
                            control={<Switch name="allow_closed_profiles" checked={filters.allow_closed_profiles || false} onChange={handleChange} />}
                            label={<LabelWithTooltip title="Закрытые профили" tooltipText="Разрешить взаимодействие с пользователями, у которых закрыт профиль." />}
                        />
                    </Grid>
                )}
                <Grid item xs={12}>
                    <FormControl fullWidth size="small">
                        <InputLabel>Был(а) в сети</InputLabel>
                        <Select name="last_seen_hours" value={filters.last_seen_hours || 0} label="Был(а) в сети" onChange={handleChange}>
                            <MenuItem value={0}>Неважно</MenuItem>
                            <MenuItem value={1}>В течение часа</MenuItem>
                            <MenuItem value={3}>В течение 3 часов</MenuItem>
                            <MenuItem value={12}>В течение 12 часов</MenuItem>
                            <MenuItem value={24}>В течение суток</MenuItem>
                        </Select>
                    </FormControl>
                </Grid>
                <Grid item xs={12}>
                    <FormControl fullWidth size="small">
                        <InputLabel>Пол</InputLabel>
                        <Select name="sex" value={filters.sex || 0} label="Пол" onChange={handleChange}>
                            <MenuItem value={0}>Любой</MenuItem>
                            <MenuItem value={1}>Женский</MenuItem>
                            <MenuItem value={2}>Мужской</MenuItem>
                        </Select>
                    </FormControl>
                </Grid>
                 {isAcceptFriends && (
                    <>
                        <Grid item xs={6}>
                             <FormControl fullWidth size="small">
                                <InputLabel>Мин. друзей</InputLabel>
                                <Select name="min_friends" value={filters.min_friends || 0} label="Мин. друзей" onChange={handleChange}>
                                    <MenuItem value={0}>Любое</MenuItem>
                                    <MenuItem value={50}>&gt; 50</MenuItem>
                                    <MenuItem value={100}>&gt; 100</MenuItem>
                                    <MenuItem value={500}>&gt; 500</MenuItem>
                                </Select>
                            </FormControl>
                        </Grid>
                         <Grid item xs={6}>
                             <FormControl fullWidth size="small">
                                <InputLabel>Мин. подписчиков</InputLabel>
                                <Select name="min_followers" value={filters.min_followers || 0} label="Мин. подписчиков" onChange={handleChange}>
                                    <MenuItem value={0}>Любое</MenuItem>
                                    <MenuItem value={100}>&gt; 100</MenuItem>
                                    <MenuItem value={500}>&gt; 500</MenuItem>
                                    <MenuItem value={1000}>&gt; 1000</MenuItem>
                                </Select>
                            </FormControl>
                        </Grid>
                    </>
                )}
            </Grid>
        </FilterWrapper>
    );
};

// --- ИЗМЕНЕНИЕ: Добавлен export для использования в других модулях ---
export const RemoveFriendsFilters = ({ filters, onChange }) => {
    const handleChange = (e) => {
        const { name, value, type, checked } = e.target;
        const val = type === 'checkbox' ? checked : value;
        // Передаем чистое имя поля, родительский компонент сам обработает вложенность
        onChange(name, val);
    };
    return (
        <Box>
             <Typography variant="subtitle1" sx={{ mb: 2, fontWeight: 600 }}>Критерии для чистки</Typography>
            <Grid container spacing={2} alignItems="center">
                 <Grid item xs={12}>
                    <FormControlLabel
                        control={<Switch name="remove_banned" checked={filters.remove_banned !== false} onChange={handleChange} />}
                        label={<LabelWithTooltip title="Удаленные / забаненные" tooltipText="Удалить пользователей, чьи страницы были удалены или заблокированы." />}
                    />
                </Grid>
                <Grid item xs={12}>
                    <FormControl fullWidth size="small">
                        <InputLabel>Неактивные (не заходили более)</InputLabel>
                        <Select name="last_seen_days" value={filters.last_seen_days || 0} label="Неактивные (не заходили более)" onChange={handleChange}>
                           <MenuItem value={0}>Не удалять по неактивности</MenuItem>
                           <MenuItem value={30}>1 месяца</MenuItem>
                           <MenuItem value={90}>3 месяцев</MenuItem>
                           <MenuItem value={180}>6 месяцев</MenuItem>
                           <MenuItem value={365}>1 года</MenuItem>
                        </Select>
                    </FormControl>
                </Grid>
                 <Grid item xs={12}>
                    <FormControl fullWidth size="small">
                        <InputLabel>Пол</InputLabel>
                        <Select name="sex" value={filters.sex || 0} label="Пол" onChange={handleChange}>
                           <MenuItem value={0}>Любой</MenuItem>
                           <MenuItem value={1}>Женский</MenuItem>
                           <MenuItem value={2}>Мужской</MenuItem>
                        </Select>
                    </FormControl>
                </Grid>
            </Grid>
        </Box>
    );
};

// Экспорт по умолчанию для ActionModalContent, который ожидает префикс "filters."
export default function ActionModalFilters({ filters, onChange, actionKey }) {
    if (actionKey === 'remove_friends') {
        return <RemoveFriendsFilters filters={filters} onChange={(name, val) => onChange(`filters.${name}`, val)} />;
    }
    return <CommonFiltersSettings filters={filters} onChange={(name, val) => onChange(`filters.${name}`, val)} actionKey={actionKey} />;
}