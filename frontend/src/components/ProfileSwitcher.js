// --- frontend/src/components/ProfileSwitcher.js ---
import React, { useState } from 'react';
import { Box, Typography, Menu, MenuItem, Button, Avatar, ListItemIcon, ListItemText, CircularProgress, Tooltip, IconButton } from '@mui/material';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import AddIcon from '@mui/icons-material/Add';
import { useUserStore, useUserActions } from 'store/userStore';
import { useQuery } from '@tanstack/react-query';
import { getManagedProfiles } from 'api';

const ProfileSwitcher = ({ isMobile }) => {
    const { setActiveProfile } = useUserActions();
    const activeProfileId = useUserStore(state => state.activeProfileId);
    
    const { data: profiles, isLoading } = useQuery({
        queryKey: ['managedProfiles'],
        queryFn: getManagedProfiles,
    });
    
    const [anchorEl, setAnchorEl] = useState(null);
    const open = Boolean(anchorEl);

    const handleClick = (event) => setAnchorEl(event.currentTarget);
    const handleClose = () => setAnchorEl(null);

    const handleSelectProfile = (profileId) => {
        setActiveProfile(profileId);
        handleClose();
    };

    const handleAddProfile = () => {
        console.log("Add new profile clicked");
        handleClose();
    };
    
    const currentProfile = profiles?.find(p => p.id === activeProfileId);

    if (isLoading && !currentProfile) {
        return <CircularProgress size={24} />;
    }

    if (isMobile) {
        return (
            <Tooltip title="Сменить профиль">
                <IconButton onClick={handleClick}>
                    <Avatar src={currentProfile?.photo_50} sx={{ width: 32, height: 32 }} />
                </IconButton>
            </Tooltip>
        );
    }

    return (
        <>
            <Button
                onClick={handleClick}
                sx={{ color: 'text.primary', textTransform: 'none', borderRadius: 2, p: 0.5 }}
                startIcon={<Avatar src={currentProfile?.photo_50} sx={{ width: 32, height: 32 }} />}
                endIcon={<KeyboardArrowDownIcon />}
            >
                <Typography sx={{ display: { xs: 'none', md: 'block' }, fontWeight: 600, mx: 1 }}>
                    {isLoading ? 'Загрузка...' : `${currentProfile?.first_name} ${currentProfile?.last_name}`}
                </Typography>
            </Button>
            <Menu anchorEl={anchorEl} open={open} onClose={handleClose}>
                {isLoading ? (
                    <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
                        <CircularProgress size={24} />
                    </Box>
                ) : (
                    profiles?.map((profile) => (
                        <MenuItem 
                            key={profile.id} 
                            onClick={() => handleSelectProfile(profile.id)}
                            selected={profile.id === activeProfileId}
                        >
                            <ListItemIcon>
                                <Avatar src={profile.photo_50} sx={{ width: 28, height: 28 }} />
                            </ListItemIcon>
                            <ListItemText>{profile.first_name} {profile.last_name}</ListItemText>
                        </MenuItem>
                    ))
                )}
                <MenuItem onClick={handleAddProfile}>
                    <ListItemIcon>
                        <AddIcon />
                    </ListItemIcon>
                    <ListItemText>Добавить профиль</ListItemText>
                </MenuItem>
            </Menu>
        </>
    );
};

export default ProfileSwitcher;