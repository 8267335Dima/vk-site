// --- frontend/src/pages/Team/InviteMemberModal.js --- (НОВЫЙ ФАЙЛ)
import React, { useState } from 'react';
import { Dialog, DialogTitle, DialogContent, DialogActions, Button, TextField, CircularProgress } from '@mui/material';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { inviteTeamMember } from 'api';
import { toast } from 'react-hot-toast';

const InviteMemberModal = ({ open, onClose }) => {
    const queryClient = useQueryClient();
    const [vkId, setVkId] = useState('');

    const mutation = useMutation({
        mutationFn: () => inviteTeamMember(Number(vkId)),
        onSuccess: () => {
            toast.success("Приглашение отправлено!");
            queryClient.invalidateQueries({ queryKey: ['myTeam'] });
            onClose();
            setVkId('');
        },
        onError: (err) => toast.error(err.response?.data?.detail || "Ошибка приглашения"),
    });

    const handleInvite = () => {
        if (!vkId || isNaN(Number(vkId))) {
            toast.error("Введите корректный VK ID пользователя.");
            return;
        }
        mutation.mutate();
    };

    return (
        <Dialog open={open} onClose={onClose} fullWidth maxWidth="xs">
            <DialogTitle>Пригласить в команду</DialogTitle>
            <DialogContent>
                <TextField
                    autoFocus
                    margin="dense"
                    label="VK ID пользователя"
                    fullWidth
                    variant="outlined"
                    value={vkId}
                    onChange={(e) => setVkId(e.target.value)}
                    placeholder="Например: 12345678"
                    helperText="Пользователь уже должен быть зарегистрирован в Zenith."
                />
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose} disabled={mutation.isLoading}>Отмена</Button>
                <Button onClick={handleInvite} variant="contained" disabled={mutation.isLoading}>
                    {mutation.isLoading ? <CircularProgress size={24} /> : "Пригласить"}
                </Button>
            </DialogActions>
        </Dialog>
    );
};

export default InviteMemberModal;