// frontend/src/pages/Dashboard/components/LimitsWidget.js
import React from 'react';
import { Paper, Typography, Box, Grid, CircularProgress, alpha, Tooltip, Skeleton } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from 'api';
import ThumbUpIcon from '@mui/icons-material/ThumbUp';
import PersonAddIcon from '@mui/icons-material/PersonAdd';

const fetchLimits = async () => {
    const { data } = await apiClient.get('/api/v1/users/me/limits');
    return data;
};

const LimitCircle = ({ value, limit, label, icon, color }) => {
    const progress = limit > 0 ? (value / limit) * 100 : 0;

    return (
        <Tooltip title={`${label}: ${value} из ${limit}`} placement="top" arrow>
            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1.5 }}>
                <Box sx={{ position: 'relative', display: 'inline-flex' }}>
                    <CircularProgress
                        variant="determinate"
                        sx={{ color: (theme) => alpha(theme.palette[color].main, 0.1) }}
                        size={80}
                        thickness={5}
                        value={100}
                    />
                    <CircularProgress
                        variant="determinate"
                        value={progress > 100 ? 100 : progress} // Cap progress at 100%
                        size={80}
                        thickness={5}
                        sx={{
                            color: (theme) => theme.palette[color].main,
                            position: 'absolute',
                            left: 0,
                            '& .MuiCircularProgress-circle': { strokeLinecap: 'round', transition: 'stroke-dashoffset 0.5s ease 0s' },
                        }}
                    />
                    <Box
                        sx={{ top: 0, left: 0, bottom: 0, right: 0, position: 'absolute', display: 'flex', alignItems: 'center', justifyContent: 'center', color: (theme) => theme.palette[color].light, }}
                    >
                        {icon}
                    </Box>
                </Box>
                <Typography variant="h6" fontWeight={600}>{value} / {limit}</Typography>
                <Typography variant="body2" color="text.secondary">{label}</Typography>
            </Box>
        </Tooltip>
    );
};

export default function LimitsWidget() {
    const { data, isLoading } = useQuery({ queryKey: ['dailyLimits'], queryFn: fetchLimits, refetchInterval: 30000 }); // Обновляем каждые 30 сек

    if (isLoading) {
        return <Skeleton variant="rounded" height={180} />;
    }

    return (
        <Paper sx={{ p: 3, height: '100%' }}>
            <Typography variant="h6" sx={{ fontWeight: 600, mb: 3, textAlign: 'center' }}>Суточная активность</Typography>
            <Grid container spacing={2} justifyContent="space-around">
                <Grid item>
                    <LimitCircle
                        value={data?.likes_today || 0}
                        limit={data?.likes_limit || 0}
                        label="Лайки"
                        icon={<ThumbUpIcon />}
                        color="primary"
                    />
                </Grid>
                <Grid item>
                    <LimitCircle
                        value={data?.friends_add_today || 0}
                        limit={data?.friends_add_limit || 0}
                        label="Заявки"
                        icon={<PersonAddIcon />}
                        color="success"
                    />
                </Grid>
            </Grid>
        </Paper>
    );
}