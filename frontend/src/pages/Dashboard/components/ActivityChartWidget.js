// frontend/src/pages/Dashboard/components/ActivityChartWidget.js
import React, { useState, useMemo } from 'react';
import { Paper, Typography, Box, useTheme, ButtonGroup, Button, Skeleton } from '@mui/material';
import Chart from 'react-apexcharts';
import { useQuery } from '@tanstack/react-query';
import { fetchActivityStats } from 'api';
import { dashboardContent } from 'content/dashboardContent';

export default function ActivityChartWidget() {
    const [days, setDays] = useState(7);
    const theme = useTheme();
    const { activityChart: content } = dashboardContent;

const { data: statsData, isLoading } = useQuery({
    queryKey: ['activityStats', days],
    queryFn: () => fetchActivityStats(days),
    placeholderData: (prev) => prev,
});

// --- КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: Преобразуем данные в безопасный формат для временной шкалы ---
// Формат [timestamp, value] является самым надежным для ApexCharts
const series = useMemo(() => {
    const data = statsData?.data || [];
    // Возвращаем пустые массивы, чтобы график не ломался при отсутствии данных
    if (data.length === 0) {
        return [
            { name: content.series.likes, data: [] },
            { name: content.series.requests, data: [] },
            { name: content.series.accepted, data: [] },
        ];
    }
    return [
        { name: content.series.likes, data: data.map(item => [new Date(item.date).getTime(), item.likes]) },
        { name: content.series.requests, data: data.map(item => [new Date(item.date).getTime(), item.friends_added]) },
        { name: content.series.accepted, data: data.map(item => [new Date(item.date).getTime(), item.requests_accepted]) },
    ];
}, [statsData, content.series]);

const options = {
    chart: { type: 'area', height: '100%', toolbar: { show: false }, zoom: { enabled: false } },
    dataLabels: { enabled: false },
    stroke: { curve: 'smooth', width: 3 },
    // --- ИСПРАВЛЕНИЕ: Используем ось типа 'datetime' вместо 'categories' ---
    xaxis: {
        type: 'datetime',
        labels: {
            format: 'dd MMM', // ApexCharts сам отформатирует дату
            style: { colors: theme.palette.text.secondary }
        },
        tooltip: { enabled: false }
    },
    yaxis: { labels: { style: { colors: theme.palette.text.secondary } } },
    tooltip: {
        theme: theme.palette.mode,
        x: { format: 'dd MMMM yyyy' } // Формат для всплывающей подсказки
    },
    fill: { type: 'gradient', gradient: { shadeIntensity: 1, opacityFrom: 0.7, opacityTo: 0.1, stops: [0, 100] } },
    colors: [theme.palette.primary.main, theme.palette.success.main, theme.palette.warning.main],
    legend: { show: true, position: 'top', horizontalAlign: 'right', fontWeight: 500 },
    grid: { borderColor: theme.palette.divider, strokeDashArray: 4 }
};

return (
    <Paper sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column' }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6" sx={{ fontWeight: 600 }}>{content.title}</Typography>
            <ButtonGroup size="small">
                <Button variant={days === 7 ? 'contained' : 'outlined'} onClick={() => setDays(7)}>{content.periods.week}</Button>
                <Button variant={days === 30 ? 'contained' : 'outlined'} onClick={() => setDays(30)}>{content.periods.month}</Button>
            </ButtonGroup>
        </Box>
        <Box sx={{ flexGrow: 1, minHeight: 280, position: 'relative' }}>
            {(isLoading && !statsData) ? (
                <Skeleton variant="rounded" height={280} />
            ) : (
                <Chart options={options} series={series} type="area" height="100%" width="100%" />
            )}
        </Box>
    </Paper>
);
}