// frontend/src/pages/Dashboard/components/AudienceAnalyticsWidget.js
import React, { useMemo } from 'react';
import { Paper, Typography, useTheme, Grid, Skeleton, Tooltip, IconButton, Stack, alpha, Box } from '@mui/material';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip as RechartsTooltip, PieChart, Pie, Cell, Legend } from 'recharts';
import { useQuery } from '@tanstack/react-query';
import { fetchAudienceAnalytics } from 'api.js';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';

const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
        return (
            <Paper sx={{ p: 2, background: 'rgba(30, 31, 37, 0.9)', backdropFilter: 'blur(5px)', borderRadius: 2 }}>
                <Typography variant="body2">{`${label}: ${payload[0].value}`}</Typography>
            </Paper>
        );
    }
    return null;
};

export default function AudienceAnalyticsWidget() {
    const theme = useTheme();
    const { data, isLoading, isError } = useQuery({ queryKey: ['audienceAnalytics'], queryFn: fetchAudienceAnalytics, staleTime: 1000 * 60 * 60 });

    const chartData = useMemo(() => {
        return {
            city: data?.city_distribution || [],
            age: data?.age_distribution || [],
            sex: data?.sex_distribution || [],
        };
    }, [data]);
    
    const COLORS = [theme.palette.primary.main, theme.palette.secondary.main, theme.palette.warning.main, theme.palette.success.main, theme.palette.info.main];

    const renderContent = () => {
        if (isLoading) return <Skeleton variant="rounded" height={250} />;
        if (isError) return <Typography color="error.main">Ошибка загрузки аналитики.</Typography>;
        if (!data || !data.sex_distribution || data.sex_distribution.length === 0) return <Box sx={{display: 'flex', height: 250, alignItems: 'center', justifyContent: 'center'}}><Typography color="text.secondary">Нет данных для анализа.</Typography></Box>;

        return (
            <Grid container spacing={3} alignItems="center">
                <Grid item xs={12} sm={4}>
                    <Typography variant="subtitle1" sx={{ fontWeight: 600, textAlign: 'center', mb: 1 }}>Пол</Typography>
                    <ResponsiveContainer width="100%" height={220}>
                        <PieChart>
                            <Pie data={chartData.sex} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label>
                                {chartData.sex.map((entry, index) => <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />)}
                            </Pie>
                             <RechartsTooltip content={<CustomTooltip />} />
                            <Legend />
                        </PieChart>
                    </ResponsiveContainer>
                </Grid>
                 <Grid item xs={12} sm={8}>
                    <Typography variant="subtitle1" sx={{ fontWeight: 600, textAlign: 'center', mb: 1 }}>Топ городов</Typography>
                     <ResponsiveContainer width="100%" height={220}>
                        <BarChart data={chartData.city} layout="vertical" margin={{ top: 5, right: 20, left: 30, bottom: 5 }}>
                             <XAxis type="number" hide />
                             <YAxis type="category" dataKey="name" width={80} tick={{ fill: theme.palette.text.secondary, fontSize: '0.8rem' }} />
                             <RechartsTooltip content={<CustomTooltip />} cursor={{ fill: alpha(theme.palette.primary.main, 0.1) }}/>
                             <Bar dataKey="value" barSize={20}>
                                 {chartData.city.map((entry, index) => <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />)}
                             </Bar>
                         </BarChart>
                     </ResponsiveContainer>
                 </Grid>
            </Grid>
        );
    };

    return (
        <Paper sx={{ p: 3, height: '100%' }}>
             <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
                <Typography variant="h6" sx={{ fontWeight: 600, m: 0 }}>Анализ аудитории</Typography>
                <Tooltip title="Анализ проводится по топ-1000 друзей. Данные кешируются на 6 часов." arrow>
                    <IconButton size="small"><InfoOutlinedIcon fontSize='small' /></IconButton>
                </Tooltip>
             </Stack>
            {renderContent()}
        </Paper>
    );
}