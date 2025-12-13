package edu.university.phdtracker.integration;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

@Component
public class WhatsAppService {

    private static final Logger log = LoggerFactory.getLogger(WhatsAppService.class);

    public void sendWhatsAppMessage(String phoneNumber, String message) {
        // TODO Integrate with real WhatsApp API provider
        log.info("Sending WhatsApp message to {}: {}", phoneNumber, message);
    }
}

