// frontend/src/pages/Dashboard/components/FunnelChartWidget.js
import React, { useMemo } from 'react';
import { Paper, Typography, Box, useTheme, Skeleton } from '@mui/material';
import Chart from 'react-apexcharts';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from 'api';

const fetchFunnelData = async () => {
    const { data } = await apiClient.get('/api/v1/analytics/friends-funnel?days=30');
    return data;
};

export default function FunnelChartWidget() {
    const theme = useTheme();
    const { data, isLoading, isError } = useQuery({
        queryKey: ['friendsFunnel'],
        queryFn: fetchFunnelData,
        staleTime: 1000 * 60 * 60, // 1 час
    });

    // --- КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: Гарантируем, что данные всегда имеют правильный формат ---
    const chartConfig = useMemo(() => {
        const funnelData = data?.funnel || [];

        // Если данных нет, возвращаем пустую, но валидную структуру
        if (funnelData.length === 0) {
            return {
                series: [{ name: 'Пользователи', data: [] }],
                categories: []
            };
        }
        
        return {
            series: [{ name: 'Пользователи', data: funnelData.map(stage => stage.value) }],
            categories: funnelData.map(stage => stage.stage_name)
        };
    }, [data]);


    const options = {
        chart: { type: 'bar', height: 200, toolbar: { show: false } }, // Изменен тип на 'bar' для большей гибкости
        plotOptions: {
            bar: {
                borderRadius: 4,
                horizontal: true,
                barHeight: '60%',
                isFunnel: true, // Включаем режим воронки
            },
        },
        dataLabels: {
            enabled: true,
            formatter: (val, opt) => chartConfig.categories[opt.dataPointIndex] + ': ' + val,
            dropShadow: { enabled: true },
            style: { colors: [theme.palette.common.white] }
        },
        xaxis: {
            categories: chartConfig.categories,
            labels: { show: false }, // Скрываем метки, т.к. они внутри столбиков
            axisBorder: { show: false },
            axisTicks: { show: false },
        },
        yaxis: { labels: { show: false } },
        legend: { show: false },
        grid: { show: false }, // Убираем сетку для чистоты
        colors: [theme.palette.primary.main, theme.palette.success.main],
    };

    const renderContent = () => {
        if (isLoading) {
            return <Skeleton variant="rectangular" height={200} sx={{ borderRadius: 2 }} />;
        }
        if (isError) {
            return <Typography color="error.main" sx={{ p: 2 }}>Ошибка загрузки.</Typography>;
        }
        if (!chartConfig.categories.length || chartConfig.series[0].data.every(v => v === 0)) {
            return <Typography color="text.secondary" sx={{ p: 2 }}>Нет данных для воронки.</Typography>;
        }
        return <Chart options={options} series={chartConfig.series} type="bar" height={200} />;
    };

    return (
        <Paper sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column' }}>
            <Typography variant="h6" gutterBottom sx={{ fontWeight: 600, mb: 2 }}>
                Воронка друзей (30 дней)
            </Typography>
            <Box sx={{ flexGrow: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                {renderContent()}
            </Box>
        </Paper>
    );
}