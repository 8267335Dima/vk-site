// frontend/src/pages/Dashboard/components/ProxyManagerModal.js
import React, { useState } from 'react';
import { Dialog, DialogTitle, DialogContent, DialogActions, Button, TextField, Box, CircularProgress, Stack, List, ListItem, ListItemText, IconButton, Typography } from '@mui/material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'react-hot-toast';
import { apiClient } from 'api';
import DeleteIcon from '@mui/icons-material/Delete';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';

const fetchProxies = async () => (await apiClient.get('/api/v1/proxies')).data;
const addProxy = async (proxyUrl) => (await apiClient.post('/api/v1/proxies', { proxy_url: proxyUrl })).data;
const deleteProxy = async (proxyId) => (await apiClient.delete(`/api/v1/proxies/${proxyId}`));

const ProxyManagerModal = ({ open, onClose }) => {
    const queryClient = useQueryClient();
    const [newProxy, setNewProxy] = useState('');

    const { data: proxies, isLoading } = useQuery({
        queryKey: ['proxies'],
        queryFn: fetchProxies,
        enabled: open, // Загружаем данные только когда модальное окно открыто
    });

    const addMutation = useMutation({
        mutationFn: addProxy,
        onSuccess: () => {
            toast.success("Прокси успешно добавлен и проверен!");
            queryClient.invalidateQueries({ queryKey: ['proxies'] });
            setNewProxy('');
        },
        onError: (err) => toast.error(err.response?.data?.detail || 'Ошибка добавления прокси'),
    });

    const deleteMutation = useMutation({
        mutationFn: deleteProxy,
        onSuccess: () => {
            toast.success("Прокси удален.");
            queryClient.invalidateQueries({ queryKey: ['proxies'] });
        },
        onError: (err) => toast.error(err.response?.data?.detail || 'Ошибка удаления'),
    });

    const handleAddProxy = () => {
        if (!newProxy.trim()) {
            toast.error("Поле не может быть пустым");
            return;
        }
        addMutation.mutate(newProxy.trim());
    };

    return (
        <Dialog open={open} onClose={onClose} fullWidth maxWidth="md">
            <DialogTitle sx={{ fontWeight: 600 }}>Менеджер прокси</DialogTitle>
            <DialogContent dividers>
                <Stack spacing={3}>
                    <Box>
                        <Typography variant="h6" gutterBottom>Добавить новый прокси</Typography>
                        <Stack direction="row" spacing={2}>
                            <TextField
                                fullWidth
                                size="small"
                                label="URL прокси"
                                placeholder="http://user:pass@host:port"
                                value={newProxy}
                                onChange={(e) => setNewProxy(e.target.value)}
                                disabled={addMutation.isLoading}
                            />
                            <Button
                                variant="contained"
                                onClick={handleAddProxy}
                                disabled={addMutation.isLoading}
                                sx={{ flexShrink: 0 }}
                            >
                                {addMutation.isLoading ? <CircularProgress size={24} /> : 'Добавить'}
                            </Button>
                        </Stack>
                    </Box>
                    <Box>
                        <Typography variant="h6" gutterBottom>Сохраненные прокси</Typography>
                        {isLoading && <CircularProgress />}
                        {!isLoading && proxies?.length === 0 && <Typography color="text.secondary">У вас пока нет прокси.</Typography>}
                        <List>
                            {proxies?.map(proxy => (
                                <ListItem
                                    key={proxy.id}
                                    divider
                                    secondaryAction={
                                        <IconButton edge="end" onClick={() => deleteMutation.mutate(proxy.id)} disabled={deleteMutation.isLoading}>
                                            <DeleteIcon />
                                        </IconButton>
                                    }
                                >
                                    {proxy.is_working ? <CheckCircleIcon color="success" sx={{ mr: 1.5 }} /> : <CancelIcon color="error" sx={{ mr: 1.5 }} />}
                                    <ListItemText
                                        primary={proxy.proxy_url}
                                        secondary={proxy.check_status_message}
                                    />
                                </ListItem>
                            ))}
                        </List>
                    </Box>
                </Stack>
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose}>Закрыть</Button>
            </DialogActions>
        </Dialog>
    );
};

export default ProxyManagerModal;