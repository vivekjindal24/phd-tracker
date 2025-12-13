package edu.university.phdtracker.service.impl;

import edu.university.phdtracker.entity.Notification;
import edu.university.phdtracker.entity.NotificationChannel;
import edu.university.phdtracker.entity.User;
import edu.university.phdtracker.integration.WhatsAppService;
import edu.university.phdtracker.repository.NotificationRepository;
import edu.university.phdtracker.service.NotificationService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class NotificationServiceImpl implements NotificationService {

    private final NotificationRepository notificationRepository;
    private final WhatsAppService whatsAppService;

    @Override
    public Notification notifyUser(User user, String message, NotificationChannel channel) {
        if (channel == NotificationChannel.WHATSAPP) {
            whatsAppService.sendWhatsAppMessage(user.getWhatsappNumber(), message);
        }
        Notification notification = Notification.builder()
                .user(user)
                .message(message)
                .channel(channel)
                .build();
        return notificationRepository.save(notification);
    }
}

