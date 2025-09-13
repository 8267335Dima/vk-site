// --- frontend/src/pages/Team/AccessControlModal.js ---
import React, { useState, useEffect } from 'react';
import { Dialog, DialogTitle, DialogContent, DialogActions, Button, List, ListItem, ListItemText, Checkbox, ListItemIcon, Avatar, CircularProgress, Typography } from '@mui/material';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { updateMemberAccess } from '../../api';
import { toast } from 'react-hot-toast';

const AccessControlModal = ({ open, onClose, member }) => {
    const queryClient = useQueryClient();
    const [accesses, setAccesses] = useState([]);

    useEffect(() => {
        if (member) {
            setAccesses(member.accesses || []);
        }
    }, [member]);

    const mutation = useMutation({
        mutationFn: (newAccesses) => updateMemberAccess(member.id, newAccesses),
        onSuccess: () => {
            toast.success("Права доступа обновлены!");
            queryClient.invalidateQueries({ queryKey: ['myTeam'] });
            onClose();
        },
        onError: (err) => toast.error(err.response?.data?.detail || "Ошибка сохранения"),
    });

    const handleToggle = (profileId) => {
        setAccesses(prev => prev.map(acc => 
            acc.profile.id === profileId ? { ...acc, has_access: !acc.has_access } : acc
        ));
    };

    const handleSave = () => {
        const payload = accesses.map(acc => ({
            profile_user_id: acc.profile.id,
            has_access: acc.has_access
        }));
        mutation.mutate(payload);
    };

    return (
        <Dialog open={open} onClose={onClose} fullWidth>
            <DialogTitle>
                Настройка доступа для {member?.user_info.first_name}
            </DialogTitle>
            <DialogContent dividers>
                {accesses.length > 0 ? (
                    <List>
                        {accesses.map(access => (
                            <ListItem key={access.profile.id} button onClick={() => handleToggle(access.profile.id)}>
                                <ListItemIcon>
                                    <Avatar src={access.profile.photo_50} sx={{ width: 32, height: 32 }}/>
                                </ListItemIcon>
                                <ListItemText 
                                    primary={`${access.profile.first_name} ${access.profile.last_name}`}
                                    secondary={`ID: ${access.profile.vk_id}`}
                                />
                                <Checkbox edge="end" checked={access.has_access} />
                            </ListItem>
                        ))}
                    </List>
                ) : (
                    <Typography color="text.secondary" sx={{p: 2, textAlign: 'center'}}>
                        У вас нет подключенных профилей для предоставления доступа.
                    </Typography>
                )}
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose} disabled={mutation.isLoading}>Отмена</Button>
                <Button onClick={handleSave} variant="contained" disabled={mutation.isLoading}>
                    {mutation.isLoading ? <CircularProgress size={24} /> : "Сохранить"}
                </Button>
            </DialogActions>
        </Dialog>
    );
};

export default AccessControlModal;