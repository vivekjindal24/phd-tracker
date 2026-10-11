package edu.university.phdtracker.service;

import edu.university.phdtracker.dto.DocumentResponse;
import edu.university.phdtracker.dto.DocumentUploadRequest;
import edu.university.phdtracker.dto.MilestoneResponse;
import edu.university.phdtracker.dto.MilestoneUpdateRequest;
import edu.university.phdtracker.dto.NotificationResponse;

import java.util.List;

public interface StudentService {

    MilestoneResponse updateMilestoneProgress(Long studentUserId, Long milestoneId, MilestoneUpdateRequest request);

    DocumentResponse uploadDocument(Long studentUserId, DocumentUploadRequest request);

    List<NotificationResponse> getNotifications(Long studentUserId);
}
