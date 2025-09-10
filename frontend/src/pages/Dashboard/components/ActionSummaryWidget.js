// frontend/src/pages/Dashboard/components/ActionSummaryWidget.js
import React from 'react';
import { Paper, Typography, Box, useTheme, Skeleton, Stack, Tooltip, IconButton } from '@mui/material';
import Chart from 'react-apexcharts';
import { useQuery } from '@tanstack/react-query';
import { fetchActionSummary } from 'api';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';

export default function ActionSummaryWidget() {
    const theme = useTheme();

    const { data: summaryData, isLoading, isError } = useQuery({
        queryKey: ['actionSummary'],
        queryFn: () => fetchActionSummary(30),
        staleTime: 1000 * 60 * 15,
    });

    const series = [{
        name: "Всего действий",
        // --- ИСПРАВЛЕНИЕ: Формат данных для временной шкалы [timestamp, value] ---
        data: summaryData?.data.map(item => [new Date(item.date).getTime(), item.total_actions]) || []
    }];

    const totalActions = summaryData?.data.reduce((acc, item) => acc + item.total_actions, 0) || 0;

    const options = {
        chart: { type: 'area', height: 200, toolbar: { show: false }, zoom: { enabled: false } },
        dataLabels: { enabled: false },
        stroke: { curve: 'smooth', width: 3 },
        xaxis: {
            type: 'datetime',
            labels: { format: 'dd MMM', style: { colors: theme.palette.text.secondary } },
            tooltip: { enabled: false },
        },
        yaxis: { labels: { style: { colors: theme.palette.text.secondary } } },
        tooltip: {
            theme: theme.palette.mode,
            x: { format: 'dd MMMM yyyy' },
            y: { title: { formatter: () => 'Действий:' } }
        },
        // --- ИЗМЕНЕНИЕ: Красивый градиент ---
        fill: { type: 'gradient', gradient: { shade: 'dark', type: 'vertical', shadeIntensity: 0.5, opacityFrom: 0.7, opacityTo: 0.1, stops: [0, 100] } },
        colors: [theme.palette.secondary.main],
        grid: { borderColor: theme.palette.divider, strokeDashArray: 4 }
    };
    
    const renderContent = () => {
        if (isLoading) {
            return <Skeleton variant="rectangular" height={200} sx={{ borderRadius: 2 }} />;
        }
        if (isError) {
            return <Typography color="error.main" sx={{ p: 2 }}>Ошибка загрузки данных.</Typography>;
        }
        if (!summaryData?.data || totalActions === 0) {
            return <Typography color="text.secondary" sx={{ p: 2 }}>Нет данных. Запустите задачи, чтобы увидеть прогресс.</Typography>;
        }
        return <Chart options={options} series={series} type="area" height={200} width="100%" />;
    };

    return (
        <Paper sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column' }}>
            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
                <Box>
                    <Typography variant="h6" sx={{ fontWeight: 600 }}>Общая динамика действий</Typography>
                    <Typography variant="body2" color="text.secondary">Всего за 30 дней: {totalActions}</Typography>
                </Box>
                <Tooltip title="График суммирует все выполненные действия (лайки, добавления и т.д.) за каждый день." arrow>
                    <IconButton size="small"><InfoOutlinedIcon fontSize='small' /></IconButton>
                </Tooltip>
             </Stack>
            <Box sx={{ flexGrow: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                {renderContent()}
            </Box>
        </Paper>
    );
}