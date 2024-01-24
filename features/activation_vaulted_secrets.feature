
Feature: Submit vaulted secrets to activation creation form

    Scenario: Submit vaulted secrets to activation creation form
        Given I am on the activation creation page
        When I submit the form with vaulted values in the extra variables field
        Then I should be redirected to the activation detail page
        And I should see the vaulted secrets I submitted
