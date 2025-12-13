package edu.university.phdtracker.service;

import edu.university.phdtracker.entity.Notification;
import edu.university.phdtracker.entity.NotificationChannel;
import edu.university.phdtracker.entity.User;

public interface NotificationService {

    Notification notifyUser(User user, String message, NotificationChannel channel);
}

