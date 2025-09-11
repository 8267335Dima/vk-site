// frontend/src/pages/Dashboard/components/TaskLogWidget.js
import React, { useState, useRef, useCallback } from 'react';
import {
    Paper, Typography, Box, CircularProgress, Chip, Collapse, IconButton,
    FormControl, InputLabel, Select, MenuItem, Stack, alpha
} from '@mui/material';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import { useInfiniteQuery } from '@tanstack/react-query';
import { fetchTaskHistory } from 'api.js';
import { format } from 'date-fns';
import { ru } from 'date-fns/locale';
import { AnimatePresence, motion } from 'framer-motion';

const statusMap = {
    SUCCESS: { label: 'Успешно', color: 'success' },
    FAILURE: { label: 'Ошибка', color: 'error' },
    PENDING: { label: 'В очереди', color: 'info' },
    STARTED: { label: 'Выполняется', color: 'warning' },
    RETRY: { label: 'Повтор', color: 'secondary' },
};

const TaskEntry = React.memo(({ task }) => {
    const [open, setOpen] = useState(false);
    const statusInfo = statusMap[task.status] || { label: task.status, color: 'default' };

    return (
        <motion.div
            layout
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, transition: { duration: 0.1 } }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
        >
            <Paper variant="outlined" sx={{ mb: 1.5, bgcolor: 'background.default', transition: 'box-shadow 0.2s', '&:hover': { boxShadow: 3 } }}>
                <Box
                    sx={{ p: 2, display: 'flex', alignItems: 'center', gap: 2, cursor: task.parameters ? 'pointer' : 'default' }}
                    onClick={() => task.parameters && setOpen(!open)}
                >
                    <Box sx={{ width: 40, flexShrink: 0 }}>
                        {task.parameters && <IconButton size="small">{open ? <KeyboardArrowUpIcon /> : <KeyboardArrowDownIcon />}</IconButton>}
                    </Box>
                    <Typography variant="body2" sx={{ width: 160, flexShrink: 0, color: 'text.secondary' }}>
                        {format(new Date(task.created_at), 'd MMM yyyy, HH:mm', { locale: ru })}
                    </Typography>
                    <Typography sx={{ flexGrow: 1, fontWeight: 500 }}>{task.task_name}</Typography>
                    <Chip label={statusInfo.label} color={statusInfo.color} size="small" variant="outlined" />
                </Box>
                <Collapse in={open} timeout="auto" unmountOnExit>
                    <Box sx={{ px: 2, pb: 2, pl: '72px' }}>
                        <Box sx={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: '0.8rem', bgcolor: (theme) => alpha(theme.palette.divider, 0.3), p: 1.5, borderRadius: 2 }}>
                            <Typography variant="caption" display="block">ID Задачи: {task.celery_task_id || 'N/A'}</Typography>
                            {task.result && <Typography variant="caption" display="block">Результат: {task.result}</Typography>}
                            {task.parameters && <Typography variant="caption">Параметры: {JSON.stringify(task.parameters, null, 2)}</Typography>}
                        </Box>
                    </Box>
                </Collapse>
            </Paper>
        </motion.div>
    );
});

export default function TaskLogWidget() {
    const [statusFilter, setStatusFilter] = useState('');
    
    const {
        data,
        error,
        fetchNextPage,
        hasNextPage,
        isFetching,
        isFetchingNextPage,
        status,
    } = useInfiniteQuery({
        queryKey: ['task_history', statusFilter],
        queryFn: ({ pageParam = 1 }) => fetchTaskHistory({ pageParam }, { status: statusFilter || undefined }),
        getNextPageParam: (lastPage) => (lastPage.has_more ? lastPage.page + 1 : undefined),
        initialPageParam: 1,
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
        <Paper sx={{ p: 3, display: 'flex', flexDirection: 'column', height: '100%', minHeight: '500px' }}>
            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
                <Typography variant="h6" sx={{ fontWeight: 600 }}>Журнал задач</Typography>
                <FormControl sx={{ minWidth: 200 }} size="small">
                    <InputLabel>Статус</InputLabel>
                    <Select value={statusFilter} label="Статус" onChange={(e) => setStatusFilter(e.target.value)}>
                        <MenuItem value=""><em>Все статусы</em></MenuItem>
                        {Object.entries(statusMap).map(([key, value]) => (
                            <MenuItem key={key} value={key}>{value.label}</MenuItem>
                        ))}
                    </Select>
                </FormControl>
            </Stack>

            <Box sx={{ flexGrow: 1, overflowY: 'auto', pr: 1, maxHeight: '600px' }}>
                {status === 'pending' && <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}><CircularProgress /></Box>}
                {status === 'error' && <Typography color="error">Ошибка: {error.message}</Typography>}
                
                <AnimatePresence>
                    {data?.pages.map((page, i) => (
                        <React.Fragment key={i}>
                            {page.items.map((task, index) => (
                                <div ref={page.items.length === index + 1 ? lastTaskElementRef : null} key={task.id}>
                                    <TaskEntry task={task} />
                                </div>
                            ))}
                        </React.Fragment>
                    ))}
                </AnimatePresence>

                {isFetchingNextPage && <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}><CircularProgress size={30} /></Box>}
                {!hasNextPage && data?.pages[0]?.items.length > 0 &&
                    <Typography textAlign="center" color="text.secondary" sx={{ mt: 2 }}>Вы загрузили всю историю.</Typography>
                }
                {!data?.pages[0]?.items.length && !isFetching &&
                    <Typography textAlign="center" color="text.secondary" sx={{ mt: 4 }}>Здесь пока нет записей. Запустите задачу, и она появится в истории.</Typography>
                }
            </Box>
        </Paper>
    );
}