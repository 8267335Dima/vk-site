// --- frontend/src/pages/Dashboard/components/ActivityChartWidget.js ---
import React, { useState, useMemo } from 'react';
import { Paper, Typography, Box, useTheme, ButtonGroup, Button, Skeleton } from '@mui/material';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid, Legend } from 'recharts';
import { useQuery } from '@tanstack/react-query';
// ИСПРАВЛЕНО
import { fetchActivityStats } from '../../../api';
import { format } from 'date-fns';
import { ru } from 'date-fns/locale';
import { motion } from 'framer-motion';

// ... (остальной код без изменений)
const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
        return (
            <Paper sx={{ p: 2, background: 'rgba(30, 31, 37, 0.9)', backdropFilter: 'blur(5px)', borderRadius: 2 }}>
                <Typography variant="body2" sx={{ mb: 1, fontWeight: 600 }}>{format(new Date(label), 'd MMMM yyyy', { locale: ru })}</Typography>
                {payload.map(p => (
                    <Typography key={p.name} variant="body2" sx={{ color: p.color }}>
                        {`${p.name}: ${p.value}`}
                    </Typography>
                ))}
            </Paper>
        );
    }
    return null;
};

export default function ActivityChartWidget() {
    const [days, setDays] = useState(7);
    const theme = useTheme();

    const { data: statsData, isLoading } = useQuery({
        queryKey: ['activityStats', days],
        queryFn: () => fetchActivityStats(days),
        placeholderData: (prev) => prev,
    });

    const series = useMemo(() => {
        return statsData?.data.map(item => ({
            date: new Date(item.date).getTime(),
            Лайки: item.likes,
            "Отправлено заявок": item.friends_added,
            "Принято заявок": item.requests_accepted
        })) || [];
    }, [statsData]);

    const renderContent = () => {
        if ((isLoading && !statsData) || !series) {
            return <Skeleton variant="rounded" height={280} />;
        }

        if (series.length === 0) {
            return <Box sx={{display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center'}}><Typography color="text.secondary">Нет данных для отображения.</Typography></Box>;
        }

        return (
            <ResponsiveContainer width="100%" height={280}>
                <AreaChart data={series} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                    <defs>
                        <linearGradient id="colorLikes" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor={theme.palette.primary.main} stopOpacity={0.8}/>
                            <stop offset="95%" stopColor={theme.palette.primary.main} stopOpacity={0}/>
                        </linearGradient>
                        <linearGradient id="colorRequests" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor={theme.palette.success.main} stopOpacity={0.8}/>
                            <stop offset="95%" stopColor={theme.palette.success.main} stopOpacity={0}/>
                        </linearGradient>
                        <linearGradient id="colorAccepted" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor={theme.palette.warning.main} stopOpacity={0.8}/>
                            <stop offset="95%" stopColor={theme.palette.warning.main} stopOpacity={0}/>
                        </linearGradient>
                    </defs>
                    <XAxis 
                        dataKey="date" 
                        stroke={theme.palette.text.secondary} 
                        tickFormatter={(timeStr) => format(new Date(timeStr), 'd MMM', { locale: ru })}
                        fontSize="0.8rem"
                    />
                    <YAxis stroke={theme.palette.text.secondary} fontSize="0.8rem" />
                    <CartesianGrid strokeDasharray="3 3" stroke={theme.palette.divider} />
                    <Tooltip content={<CustomTooltip />} />
                    <Legend />
                    <Area type="monotone" dataKey="Лайки" stroke={theme.palette.primary.main} fillOpacity={1} fill="url(#colorLikes)" strokeWidth={2.5} activeDot={{ r: 6 }} />
                    <Area type="monotone" dataKey="Отправлено заявок" stroke={theme.palette.success.main} fillOpacity={1} fill="url(#colorRequests)" strokeWidth={2.5} activeDot={{ r: 6 }}/>
                    <Area type="monotone" dataKey="Принято заявок" stroke={theme.palette.warning.main} fillOpacity={1} fill="url(#colorAccepted)" strokeWidth={2.5} activeDot={{ r: 6 }}/>
                </AreaChart>
            </ResponsiveContainer>
        );
    }

    return (
        <Paper sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column' }} component={motion.div} initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="h6" sx={{ fontWeight: 600 }}>Статистика активности</Typography>
                <ButtonGroup size="small">
                    <Button variant={days === 7 ? 'contained' : 'outlined'} onClick={() => setDays(7)}>Неделя</Button>
                    <Button variant={days === 30 ? 'contained' : 'outlined'} onClick={() => setDays(30)}>Месяц</Button>
                </ButtonGroup>
            </Box>
            <Box sx={{ flexGrow: 1, minHeight: 280, position: 'relative' }}>
                {renderContent()}
            </Box>
        </Paper>
    );
}