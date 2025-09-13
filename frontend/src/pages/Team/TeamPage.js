// --- frontend/src/pages/Team/TeamPage.js ---
import React, { useState } from 'react';
import { Container, Typography, Box, Button, CircularProgress, Paper, Stack, Avatar, IconButton, Tooltip, alpha } from '@mui/material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchMyTeam, removeTeamMember } from '../../api';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';
import AccessControlModal from './AccessControlModal';
import InviteMemberModal from './InviteMemberModal';
import { toast } from 'react-hot-toast';

const TeamMemberCard = ({ member, onEditAccess, onDelete, isOwner }) => (
    <Paper sx={{ p: 2, display: 'flex', alignItems: 'center', gap: 2 }}>
        <Avatar src={member.user_info.photo_50} />
        <Box sx={{ flexGrow: 1 }}>
            <Typography variant="h6">{member.user_info.first_name} {member.user_info.last_name}</Typography>
            <Typography variant="body2" color="text.secondary">{isOwner ? 'Владелец' : 'Участник'}</Typography>
        </Box>
        <Tooltip title="Настроить доступ">
            <span>
                <IconButton onClick={() => onEditAccess(member)} disabled={isOwner}><EditIcon /></IconButton>
            </span>
        </Tooltip>
        <Tooltip title="Удалить из команды">
            <span>
                <IconButton onClick={() => onDelete(member.id)} disabled={isOwner}><DeleteIcon color={isOwner ? 'disabled' : "error"} /></IconButton>
            </span>
        </Tooltip>
    </Paper>
);

const TeamPage = () => {
    const queryClient = useQueryClient();
    const [accessModal, setAccessModal] = useState({ open: false, member: null });
    const [isInviteModalOpen, setInviteModalOpen] = useState(false);
    
    const { data: team, isLoading } = useQuery({ queryKey: ['myTeam'], queryFn: fetchMyTeam });

    const deleteMutation = useMutation({
        mutationFn: removeTeamMember,
        onSuccess: () => {
            toast.success("Участник удален из команды.");
            queryClient.invalidateQueries({ queryKey: ['myTeam'] });
        },
        onError: (err) => toast.error(err.response?.data?.detail || "Ошибка удаления"),
    });

    const handleDeleteMember = (memberId) => {
        if (window.confirm("Вы уверены, что хотите удалить этого участника из команды?")) {
            deleteMutation.mutate(memberId);
        }
    };

    const handleOpenAccessModal = (member) => {
        setAccessModal({ open: true, member });
    };

    return (
        <Container maxWidth="md" sx={{ py: 4 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
                <Typography variant="h4" component="h1" sx={{ fontWeight: 600 }}>
                    {isLoading ? 'Загрузка...' : `Команда "${team?.name}"`}
                </Typography>
                <Button variant="contained" startIcon={<AddIcon />} onClick={() => setInviteModalOpen(true)}>
                    Пригласить участника
                </Button>
            </Box>

            {isLoading ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}><CircularProgress /></Box>
            ) : (
                <Stack spacing={2}>
                    {team?.members && team.members.length > 0 ? (
                        team.members.map(member => (
                            <TeamMemberCard 
                                key={member.id} 
                                member={member} 
                                onEditAccess={handleOpenAccessModal}
                                onDelete={handleDeleteMember}
                                isOwner={member.user_id === team.owner_id}
                            />
                        ))
                    ) : (
                        <Paper sx={{ p: 5, textAlign: 'center', backgroundColor: (theme) => alpha(theme.palette.primary.main, 0.05), borderStyle: 'dashed' }}>
                            <Typography variant="h6" gutterBottom>В вашей команде пока нет участников</Typography>
                            <Typography color="text.secondary">Нажмите "Пригласить", чтобы добавить SMM-менеджеров и выдать им доступ к клиентским проектам.</Typography>
                        </Paper>
                    )}
                </Stack>
            )}

            {accessModal.member && (
                <AccessControlModal
                    open={accessModal.open}
                    onClose={() => setAccessModal({ open: false, member: null })}
                    member={accessModal.member}
                />
            )}
            <InviteMemberModal
                open={isInviteModalOpen}
                onClose={() => setInviteModalOpen(false)}
            />
        </Container>
    );
};

export default TeamPage;