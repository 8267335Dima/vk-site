// --- frontend/src/pages/Dashboard/components/ActionModalFilters.js ---
import React from 'react';
import {
    FormControlLabel, Switch, Select, MenuItem, InputLabel, FormControl, Grid, Typography, Box, Tooltip, TextField, Divider
} from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { content } from 'content/content';
import PresetManager from './PresetManager';

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

const NumberFilterField = ({ name, value, label, onChange }) => (
    <TextField
        name={name}
        value={value || ''}
        onChange={onChange}
        label={label}
        type="number"
        size="small"
        fullWidth
        placeholder="Любое"
        inputProps={{ min: 0 }}
        helperText="Оставьте пустым, чтобы не использовать"
    />
);


export const CommonFiltersSettings = ({ filters, onChange, actionKey }) => {
    const showClosedProfilesFilter = ['accept_friends', 'add_recommended', 'mass_messaging'].includes(actionKey);
    const isAcceptFriends = actionKey === 'accept_friends';

    const handleChange = (e) => {
        const { name, value, type, checked } = e.target;
        const val = type === 'checkbox' ? checked : (type === 'number' ? (value ? parseInt(value, 10) : null) : value);
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
                            label={<LabelWithTooltip title="Закрытые профили" tooltipText="Разрешить взаимодействие с пользователями, у которых закрыт профиль. Часть фильтров (статус, кол-во друзей) не будет применяться." />}
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
                <Grid item xs={12}>
                    <TextField
                        name="status_keyword"
                        value={filters.status_keyword || ''}
                        onChange={handleChange}
                        label="Ключевое слово в статусе"
                        size="small"
                        fullWidth
                        placeholder="Например: ищу работу, спб"
                    />
                </Grid>
                 {isAcceptFriends && (
                    <>
                        <Grid item xs={6}><NumberFilterField name="min_friends" value={filters.min_friends} label="Мин. друзей" onChange={handleChange} /></Grid>
                        <Grid item xs={6}><NumberFilterField name="max_friends" value={filters.max_friends} label="Макс. друзей" onChange={handleChange} /></Grid>
                        <Grid item xs={6}><NumberFilterField name="min_followers" value={filters.min_followers} label="Мин. подписчиков" onChange={handleChange} /></Grid>
                        <Grid item xs={6}><NumberFilterField name="max_followers" value={filters.max_followers} label="Макс. подписчиков" onChange={handleChange} /></Grid>
                    </>
                )}
            </Grid>
        </FilterWrapper>
    );
};

export const RemoveFriendsFilters = ({ filters, onChange }) => {
    const handleChange = (e) => {
        const { name, value, type, checked } = e.target;
        const val = type === 'checkbox' ? checked : value;
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

const KeywordFilter = ({ title, keyword, onChange, placeholder, helperText }) => (
    <Box>
        <Typography variant="subtitle1" sx={{ mb: 2, fontWeight: 600 }}>{title}</Typography>
        <TextField
            name="status_keyword"
            value={keyword || ''}
            onChange={onChange}
            label="Ключевое слово или фраза"
            size="small"
            fullWidth
            placeholder={placeholder}
            helperText={helperText}
        />
    </Box>
);

export default function ActionModalFilters({ filters, onChange, actionKey }) {
    const onApplyPreset = (newFilters) => {
        onChange('filters', newFilters);
    };

    const automationConfig = content.automations.find(a => a.id === actionKey);
    const hasFilters = automationConfig?.has_filters ?? false;
    if (!hasFilters) return null;
    
    let FilterComponent;
    const handleChange = (e) => onChange(`filters.${e.target.name}`, e.target.value);

    switch (actionKey) {
        case 'remove_friends':
            FilterComponent = <RemoveFriendsFilters filters={filters} onChange={(name, val) => onChange(`filters.${name}`, val)} />;
            break;
        case 'leave_groups':
            FilterComponent = <KeywordFilter title="Критерии для отписки" keyword={filters.status_keyword} onChange={handleChange} placeholder="Например: барахолка, новости" helperText="Оставьте пустым, чтобы отписываться от всех подряд." />;
            break;
        case 'join_groups':
            FilterComponent = <KeywordFilter title="Критерии для вступления" keyword={filters.status_keyword} onChange={handleChange} placeholder="Например: SMM, дизайн, маркетинг" helperText="Введите ключевые слова для поиска релевантных групп." />;
            break;
        default:
            FilterComponent = <CommonFiltersSettings filters={filters} onChange={(name, val) => onChange(`filters.${name}`, val)} actionKey={actionKey} />;
    }

    return (
        <Box>
            <PresetManager actionKey={actionKey} currentFilters={filters} onApply={onApplyPreset} />
            <Divider sx={{ my: 2 }} />
            {FilterComponent}
        </Box>
    );
}