# Creating Credentials for Sources

If you have a rulebook that needs encrypted fields, you can define them in the EDA Server as Credentials with a custom Credential Type. In the example below we will explain the process with a sample rulebook

 - Defining a Custom Credential Type
 - Adding a Credential
 - Attaching the Credential to Activation

# Rulebook

The rulebook below is a sample that uses **ansible.eda.kafka** as a source plugin. It uses the SASL PLAINTEXT protocol and PLAIN mechanism. This rulebook uses 5 variables that can be passed as extra vars at runtime into the activation when run from the EDA Server.
   - sasl_plain_username
   - sasl_plain_password
   - kafka_host
   - kafka_port default is 9092
   - kafka_topic
```
---
-  name:  Kafka  Consumer
   hosts:  all
   sources:
   -  name:  Kafka
      ansible.eda.kafka:
          sasl_plain_username:  "{{ sasl_plain_username }}"
          sasl_plain_password:  "{{ sasl_plain_password }}"
          host:  "{{ kafka_host }}"
          port:  "{{ kafka_port | default(9092) }}"
          topic:  "{{ kafka_topic }}"
          security_protocol:  SASL_PLAINTEXT
          sasl_mechanism:  PLAIN
          verify_mode:  CERT_NONE
      rules:
      -  name:  r1
         condition:  true
         action:
           debug:
```

From the above rulebook we can make a Custom Credential Type that can comprises of all 5 variables or we can just choose 2 of them, the choice is entirely ours. For simplicity sake we will just use the **sasl_plain_username** and **sasl_plain_password** in our custom Credential Type.
# Custom Credential Type

In a EDA Credential Type we have **Input configuration** and **Injector configuration** which both accept a YAML or JSON data. Lets name this new credential type ***Kafka Source***
### Input configuration
The input configuration comprises an array of fields that would solicit user input. Each field can only be of string or boolean types and contains the following properties.
|Name|Description  |
|--|--|
| id | The unique identifier of the field, this can only contain alpha numeric and underscore characters. The value will be used in extra_vars. |
| label| The label which will be displayed by the UI
| type| The type of data we are expecting, string or boolean. Default string
| help_text| The text message when the user clicks on the question mark above the field. Default ""
|secret| Is this a secret field, valid values are true or false


Based on the above definition we can create a simple YAML schema that would look like the following. It has 2 fields one for username and one for password which is encrypted.
```
fields:
   - id: sasl_plain_username
     label: SASL User Name
     help_text: Please enter a username
   - id: sasl_plain_password
     label: SASL Password
     help_text: Please enter a password
     secret: true
```
### Injector configuration
The Injector is used to take the fields from inputs and map them into extra vars that can be sent to ansible-rulebook when running the activation. The Injector currently only supports extra_vars in the future we will add support for files and env. The Injector based on the input configuration would look like
```
extra_vars:
   sasl_plain_username: "{{ sasl_plain_username }}"
   sasl_plain_password: "{{ sasl_plain_password }}"
```

This maps the 2 keys that we get from the inputs, this is a simple 1 to 1 map, the Injector configuration allows us to provide defaults if the user doesn't provide a value and also allows us to change the key names. **extra_vars** is a required key when defining an Injector configuration.

# Credential
Now that we have a custom Credential Type defined in the EDA Server we can add a Credential, from the left pane in the UI select **Credentials** and then click on **Create credential** Under the Credential type you should see the ***Kafka Source*** that we  just created.
Enter the values for username and password and save this Credential with the name ***Kafka Demo***

# Attaching Credential to Activation

Create a new Rulebook Activation fill in all the fields you will see a new field called **Credential** which is a drop down the ***Kafka Demo*** should be visible in this list.
Since our rulebook expects 5 fields to be provided we will get 2 fields from the Credential Kafka Demo the other 3 would have to be provided by adding them via the **Variables** at the bottom of the screen.

In the Variables section you can set
    

 - kafka_host: <<your_kafka_server>>
 - kafka_topic: <<your_kafka_topic>>
 - kafka_port: <<your_kafka_port>>

When you start the Activation you will see the extra vars getting updated with the fields from the ***Kafka Demo*** and the user submitted variables.

# Additional attributes in a field
There are additional attributes that can be specified in the input configuration for a field.
|Name|Description  |
|--|--|
| default | The default value for the field |
| choices| An array of string values, which will be listed as a drop down and the users choices to the elements in the list |

```
fields:
   - id: sasl_plain_username
     label: SASL User Name
     help_text: Please enter a username
     default: kafka1
   - id: sasl_plain_password
     label: SASL Password
     help_text: Please enter a password
     secret: true
   - id: security_mechanism
     type: string
     label: Security Mechanism
     choices:
       - PLAIN
       - GSSAPI
       - SCRAM-SHA-256
       - SCRAM-SHA-512
       - OAUTHBEARER
     helptext: The Security Mechanism to use
```
