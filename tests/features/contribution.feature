Feature: Member Contribution via M-Pesa
  As a church member
  I want to make contributions via M-Pesa
  So that I can support the church financially

  Background:
    Given the following contribution categories exist:
      | name    | code   | is_active |
      | Tithe   | TITHE  | true      |
      | Offering| OFFER  | true      |
    And I am a registered member with phone "254712345678"

  Scenario: Successful single-category contribution
    When I initiate a contribution of "1000" to "Tithe"
    Then I should receive an M-Pesa STK push notification
    And a pending M-Pesa transaction should be created
    And a pending contribution record should be created
    When the M-Pesa payment is confirmed successful
    Then my contribution status should be "completed"
    And I should receive an SMS receipt

  Scenario: Failed contribution - User cancels payment
    When I initiate a contribution of "1000" to "Tithe"
    And I cancel the M-Pesa payment
    Then my contribution status should be "failed"
    And I should not receive an SMS receipt

  Scenario: Multi-category contribution
    When I initiate a multi-category contribution:
      | category | amount |
      | Tithe    | 1000   |
      | Offering | 500    |
    Then I should receive an M-Pesa STK push for total "1500"
    And 2 pending contribution records should be created
    And all contributions should have the same group ID
    When the M-Pesa payment is confirmed successful
    Then all contribution statuses should be "completed"
    And I should receive a combined SMS receipt

  Scenario: Contribution for guest member
    Given I am not a registered member
    When I initiate a contribution of "500" to "Offering" with phone "254798765432"
    Then a guest member account should be created for me
    And I should receive an M-Pesa STK push notification
    When the M-Pesa payment is confirmed successful
    Then my contribution should be recorded
    And I should receive an SMS receipt

  Scenario: Contribution to inactive category
    Given the "Tithe" category is inactive
    When I try to initiate a contribution of "1000" to "Tithe"
    Then I should receive an error message
    And no transaction should be created

  Scenario: Invalid contribution amount
    When I try to initiate a contribution of "0.50" to "Tithe"
    Then I should receive an error about minimum amount
    And no transaction should be created
