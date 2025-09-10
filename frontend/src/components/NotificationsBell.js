// frontend/src/components/NotificationsBell.js
import React, { useState } from 'react';
import {
    IconButton, Badge, Popover, List, ListItem, ListItemText,
    Typography, Box, CircularProgress, Divider, Chip
} from '@mui/material';
import NotificationsIcon from '@mui/icons-material/Notifications';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchNotifications, markNotificationsAsRead } from 'api';
import { formatDistanceToNow } from 'date-fns';
import { ru } from 'date-fns/locale';

const levelColors = {
    error: 'error',
    warning: 'warning',
    success: 'success',
    info: 'info',
};

function NotificationItem({ notification }) {
    return (
        <ListItem alignItems="flex-start" sx={{ opacity: notification.is_read ? 0.6 : 1 }}>
            <ListItemText
                primary={
                    <Typography variant="body2" sx={{ fontWeight: notification.is_read ? 400 : 500 }}>
                        {notification.message}
                    </Typography>
                }
                secondary={
                    <Box component="span" sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mt: 0.5 }}>
                         <Typography component="span" variant="caption" color="text.secondary">
                            {formatDistanceToNow(new Date(notification.created_at), { addSuffix: true, locale: ru })}
                        </Typography>
                        <Chip label={notification.level} color={levelColors[notification.level]} size="small" variant="outlined" />
                    </Box>
                }
            />
        </ListItem>
    );
}

export default function NotificationsBell() {
    const [anchorEl, setAnchorEl] = useState(null);
    const queryClient = useQueryClient();

    const { data, isLoading } = useQuery({
        queryKey: ['notifications'],
        queryFn: fetchNotifications,
    });

    const mutation = useMutation({
        mutationFn: markNotificationsAsRead,
        onSuccess: () => {
            queryClient.setQueryData(['notifications'], (oldData) => {
                if (!oldData) return oldData;
                return {
                    ...oldData,
                    unread_count: 0,
                    items: oldData.items.map(item => ({ ...item, is_read: true })),
                };
            });
        },
    });

    const handleClick = (event) => {
        setAnchorEl(event.currentTarget);
        if (data?.unread_count > 0) {
            mutation.mutate();
        }
    };

    const handleClose = () => {
        setAnchorEl(null);
    };

    const open = Boolean(anchorEl);
    const id = open ? 'notifications-popover' : undefined;

    return (
        <>
            <IconButton color="inherit" onClick={handleClick}>
                <Badge badgeContent={data?.unread_count || 0} color="error">
                    <NotificationsIcon />
                </Badge>
            </IconButton>
            <Popover
                id={id}
                open={open}
                anchorEl={anchorEl}
                onClose={handleClose}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
                transformOrigin={{ vertical: 'top', horizontal: 'right' }}
                slotProps={{ paper: { sx: { width: 360, maxHeight: 400, display: 'flex', flexDirection: 'column' } } }}
            >
                <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
                    <Typography variant="h6" component="div">Уведомления</Typography>
                </Box>
                
                {isLoading ? (
                    <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}><CircularProgress /></Box>
                ) : (
                    <List sx={{ p: 0, overflow: 'auto' }}>
                        {data?.items?.length > 0 ? (
                            data.items.map((notif, index) => (
                                <React.Fragment key={notif.id}>
                                    <NotificationItem notification={notif} />
                                    {index < data.items.length - 1 && <Divider component="li" />}
                                </React.Fragment>
                            ))
                        ) : (
                            <Typography sx={{ p: 2, textAlign: 'center', color: 'text.secondary' }}>
                                Здесь пока пусто
                            </Typography>
                        )}
                    </List>
                )}
            </Popover>
        </>
    );
}