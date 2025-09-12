// frontend/src/components/NotificationsBell.js (ЗНАЧИТЕЛЬНЫЕ ИЗМЕНЕНИЯ)
import React, { useState } from 'react';
import {
    IconButton, Badge, Popover, List, ListItem, ListItemText,
    Typography, Box, CircularProgress, Divider, Avatar, ListItemAvatar, alpha
} from '@mui/material';
import NotificationsIcon from '@mui/icons-material/Notifications';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchNotifications, markNotificationsAsRead } from 'api';
import { formatDistanceToNow } from 'date-fns';
import { ru } from 'date-fns/locale';

const levelConfig = {
    error: { color: 'error', icon: <ErrorOutlineIcon /> },
    warning: { color: 'warning', icon: <InfoOutlinedIcon /> },
    success: { color: 'success', icon: <CheckCircleOutlineIcon /> },
    info: { color: 'info', icon: <InfoOutlinedIcon /> },
};

function NotificationItem({ notification }) {
    const config = levelConfig[notification.level] || levelConfig.info;

    return (
        <ListItem 
            alignItems="flex-start" 
            sx={{ 
                bgcolor: notification.is_read ? 'transparent' : (theme) => alpha(theme.palette[config.color].main, 0.1),
                transition: 'background-color 0.3s',
                '&:hover': {
                    bgcolor: (theme) => alpha(theme.palette.text.primary, 0.05)
                }
            }}
        >
            <ListItemAvatar sx={{ minWidth: 40, mt: 0.5 }}>
                <Avatar sx={{ bgcolor: `${config.color}.main`, width: 32, height: 32 }}>
                    {config.icon}
                </Avatar>
            </ListItemAvatar>
            <ListItemText
                primary={
                    <Typography variant="body2" sx={{ fontWeight: notification.is_read ? 400 : 500, color: 'text.primary' }}>
                        {notification.message}
                    </Typography>
                }
                secondary={
                    <Typography component="span" variant="caption" sx={{ color: `${config.color}.light` }}>
                        {formatDistanceToNow(new Date(notification.created_at), { addSuffix: true, locale: ru })}
                    </Typography>
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
                disableScrollLock={true} // <-- ИЗМЕНЕНИЕ: Разрешаем скролл страницы
                anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
                transformOrigin={{ vertical: 'top', horizontal: 'right' }}
                slotProps={{ paper: { sx: { width: 380, maxHeight: 500, display: 'flex', flexDirection: 'column', borderRadius: 3, mt: 1.5 } } }}
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
                                    {index < data.items.length - 1 && <Divider component="li" variant="inset" />}
                                </React.Fragment>
                            ))
                        ) : (
                            <Typography sx={{ p: 3, textAlign: 'center', color: 'text.secondary' }}>
                                Здесь пока пусто
                            </Typography>
                        )}
                    </List>
                )}
            </Popover>
        </>
    );
}