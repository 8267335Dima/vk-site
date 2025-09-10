// frontend/src/pages/History/HistoryPage.js
import React, { useRef, useCallback, useState } from 'react';
import {
    Container, Typography, Box, Paper, CircularProgress,
    Chip, Collapse, IconButton, FormControl, InputLabel, Select, MenuItem
} from '@mui/material';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import { useInfiniteQuery } from '@tanstack/react-query';
import { fetchTaskHistory } from 'api';
import { format } from 'date-fns';
import { ru } from 'date-fns/locale';

const statusMap = {
    SUCCESS: { label: 'Успешно', color: 'success' },
    FAILURE: { label: 'Ошибка', color: 'error' },
    PENDING: { label: 'В очереди', color: 'warning' },
    STARTED: { label: 'Выполняется', color: 'info' },
    RETRY: { label: 'Повтор', color: 'secondary' },
};

const TaskEntry = ({ task }) => {
    const [open, setOpen] = useState(false);
    const statusInfo = statusMap[task.status] || { label: task.status, color: 'default' };

    return (
        <Paper variant="outlined" sx={{ mb: 2, bgcolor: 'neutral.main' }}>
            <Box
                sx={{ p: 2, display: 'flex', alignItems: 'center', gap: 2, cursor: task.parameters ? 'pointer' : 'default' }}
                onClick={() => task.parameters && setOpen(!open)}
            >
                <Box sx={{ width: 40, flexShrink: 0 }}>
                    {task.parameters && <IconButton size="small">{open ? <KeyboardArrowUpIcon /> : <KeyboardArrowDownIcon />}</IconButton>}
                </Box>
                <Typography variant="body2" sx={{ width: 160, flexShrink: 0 }}>{format(new Date(task.created_at), 'd MMM yyyy, HH:mm', { locale: ru })}</Typography>
                <Typography sx={{ flexGrow: 1, fontWeight: 500 }}>{task.task_name}</Typography>
                <Chip label={statusInfo.label} color={statusInfo.color} size="small" />
            </Box>
            <Collapse in={open} timeout="auto" unmountOnExit>
                <Box sx={{ px: 2, pb: 2, pl: '72px' }}>
                    <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace', bgcolor: 'background.default', p: 1.5, borderRadius: 1 }}>
                        {`ID Задачи: ${task.celery_task_id}\n`}
                        {task.result && `Результат: ${task.result}\n`}
                        Параметры: {JSON.stringify(task.parameters, null, 2)}
                    </Typography>
                </Box>
            </Collapse>
        </Paper>
    );
};

export default function HistoryPage() {
    const [statusFilter, setStatusFilter] = useState('');
    const {
        data, error, fetchNextPage, hasNextPage,
        isFetching, isFetchingNextPage, status,
    } = useInfiniteQuery({
        queryKey: ['task_history', statusFilter],
        queryFn: (context) => fetchTaskHistory(context, statusFilter || null),
        getNextPageParam: (lastPage) => lastPage.has_more ? lastPage.page + 1 : undefined,
    });

    const observer = useRef();
    const lastTaskElementRef = useCallback(node => {
        if (isFetchingNextPage) return;
        if (observer.current) observer.current.disconnect();
        observer.current = new IntersectionObserver(entries => {
            if (entries[0].isIntersecting && hasNextPage && !isFetching) {
                fetchNextPage();
            }
        });
        if (node) observer.current.observe(node);
    }, [isFetchingNextPage, fetchNextPage, hasNextPage, isFetching]);

    return (
        <Container maxWidth="lg" sx={{ py: 4 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
                <Typography variant="h4" component="h1" sx={{ fontWeight: 600 }}>
                    История Задач
                </Typography>
                <FormControl sx={{ minWidth: 200 }} size="small">
                    <InputLabel>Статус</InputLabel>
                    <Select value={statusFilter} label="Статус" onChange={(e) => setStatusFilter(e.target.value)}>
                        <MenuItem value=""><em>Все статусы</em></MenuItem>
                        {Object.keys(statusMap).map(key => (
                            <MenuItem key={key} value={key}>{statusMap[key].label}</MenuItem>
                        ))}
                    </Select>
                </FormControl>
            </Box>

            {status === 'loading' && <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}><CircularProgress /></Box>}
            {status === 'error' && <Typography color="error">Ошибка: {error.message}</Typography>}
            
            {data?.pages.map((page, i) => (
                <React.Fragment key={i}>
                    {page.items.map((task, index) => {
                        const isLastElement = page.items.length === index + 1;
                        return (
                            <div ref={isLastElement ? lastTaskElementRef : null} key={task.id}>
                                <TaskEntry task={task} />
                            </div>
                        );
                    })}
                </React.Fragment>
            ))}

            {isFetchingNextPage && <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}><CircularProgress size={30} /></Box>}
            {!hasNextPage && data?.pages[0]?.items.length > 0 &&
                <Typography textAlign="center" color="text.secondary" sx={{ mt: 2 }}>
                    Вы загрузили всю историю.
                </Typography>
            }
            {!data?.pages[0]?.items.length && !isFetching &&
                <Typography textAlign="center" color="text.secondary" sx={{ mt: 4 }}>
                    Здесь пока нет записей. Запустите задачу, и она появится в истории.
                </Typography>
            }
        </Container>
    );
}