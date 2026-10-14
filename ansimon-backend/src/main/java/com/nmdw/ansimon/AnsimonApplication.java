package com.nmdw.ansimon;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@EnableScheduling
@SpringBootApplication
public class AnsimonApplication {

    public static void main(String[] args) {
        SpringApplication.run(AnsimonApplication.class, args);
    }
}
