// frontend/src/pages/Dashboard/components/ActionModalFilters.js
import React from 'react';
import {
    FormControlLabel, Switch, Select, MenuItem, InputLabel, FormControl, Grid, Typography, Box, Tooltip
} from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { dashboardContent } from 'content/dashboardContent';

const { filters: content } = dashboardContent.modal;

const FilterWrapper = ({ children }) => (
    <Box>
        <Typography variant="subtitle1" sx={{ mb: 2, fontWeight: 600 }}>{content.title}</Typography>
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

export const CommonFiltersSettings = ({ filters, onChange, actionKey }) => {
    const showClosedProfilesFilter = ['accept_friends', 'add_recommended'].includes(actionKey);
    const isAcceptFriends = actionKey === 'accept_friends';

    return (
        <FilterWrapper>
            <Grid container spacing={2} alignItems="center">
                <Grid item xs={12} sm={6}>
                    <FormControlLabel control={<Switch name="is_online" checked={filters.is_online || false} onChange={onChange} />} label={content.onlineOnly} />
                </Grid>
                {showClosedProfilesFilter && (
                    <Grid item xs={12} sm={6}>
                        <FormControlLabel
                            control={<Switch name="allow_closed_profiles" checked={filters.allow_closed_profiles || false} onChange={onChange} />}
                            label={<LabelWithTooltip title={content.closedProfiles.label} tooltipText={content.closedProfiles.tooltip} />}
                        />
                    </Grid>
                )}
                <Grid item xs={12}>
                    <FormControl fullWidth size="small">
                        <InputLabel>{content.lastSeen.label}</InputLabel>
                        <Select name="last_seen_hours" value={filters.last_seen_hours || 0} label={content.lastSeen.label} onChange={onChange}>
                            {content.lastSeen.options.map(opt => <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>)}
                        </Select>
                    </FormControl>
                </Grid>
                <Grid item xs={12}>
                    <FormControl fullWidth size="small">
                        <InputLabel>{content.sex.label}</InputLabel>
                        <Select name="sex" value={filters.sex || 0} label={content.sex.label} onChange={onChange}>
                            {content.sex.options.map(opt => <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>)}
                        </Select>
                    </FormControl>
                </Grid>
                 {/* --- НОВЫЙ БЛОК ФИЛЬТРОВ --- */}
                {isAcceptFriends && (
                    <>
                        <Grid item xs={6}>
                             <FormControl fullWidth size="small">
                                <InputLabel>Мин. друзей</InputLabel>
                                <Select name="min_friends" value={filters.min_friends || 0} label="Мин. друзей" onChange={onChange}>
                                    {content.friendsCount.options.map(opt => <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>)}
                                </Select>
                            </FormControl>
                        </Grid>
                         <Grid item xs={6}>
                             <FormControl fullWidth size="small">
                                <InputLabel>Мин. подписчиков</InputLabel>
                                <Select name="min_followers" value={filters.min_followers || 0} label="Мин. подписчиков" onChange={onChange}>
                                    {content.followersCount.options.map(opt => <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>)}
                                </Select>
                            </FormControl>
                        </Grid>
                    </>
                )}
            </Grid>
        </FilterWrapper>
    );
};

export const RemoveFriendsFilters = ({ filters, onChange }) => {
    return (
        <Box>
             <Typography variant="subtitle1" sx={{ mb: 2, fontWeight: 600 }}>{content.title}</Typography>
            <Grid container spacing={2} alignItems="center">
                 <Grid item xs={12}>
                    <FormControlLabel
                        control={<Switch name="remove_banned" checked={filters.remove_banned} onChange={onChange} />}
                        label={<LabelWithTooltip title={content.removeBanned.label} tooltipText={content.removeBanned.tooltip} />}
                    />
                </Grid>
                <Grid item xs={12}>
                    <FormControl fullWidth size="small">
                        <InputLabel>{content.inactive.label}</InputLabel>
                        <Select name="last_seen_days" value={filters.last_seen_days || 0} label={content.inactive.label} onChange={onChange}>
                            {content.inactive.options.map(opt => <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>)}
                        </Select>
                    </FormControl>
                </Grid>
                 <Grid item xs={12}>
                    <FormControl fullWidth size="small">
                        <InputLabel>Пол</InputLabel>
                        <Select name="sex" value={filters.sex || 0} label="Пол" onChange={onChange}>
                            {content.sex.options.map(opt => <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>)}
                        </Select>
                    </FormControl>
                </Grid>
            </Grid>
        </Box>
    );
};