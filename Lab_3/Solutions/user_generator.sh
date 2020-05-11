echo "Generating LDIF for 30000 Users"
echo ""
echo ""
echo "Creating users and groups for HR organizational unit"
echo ""
echo ""

~/openldap/Lab_3/gen_dit/gen_dit.py -s ou=hr,dc=example,dc=com -n 10024 > ~/openldap/Lab_3/gen_dit/automated_user_ldif_generator.ldif ; sed -i  '1,/cn=hr/!d' ~/openldap/Lab_3/gen_dit/automated_user_ldif_generator.ldif  ; sed -i  '$d' ~/openldap/Lab_3/gen_dit/automated_user_ldif_generator.ldif

echo "Modifying User and IDs"
sed -i s/10000/21000/g ~/openldap/Lab_3/gen_dit/gen_dit.py

echo ""
echo ""
echo "Creating users and groups for IT organization unit"
echo ""
echo ""

~/openldap/Lab_3/gen_dit/gen_dit.py -s ou=it,dc=example,dc=com -n 10024 >> ~/openldap/Lab_3/gen_dit/automated_user_ldif_generator.ldif ; sed -i  '1,/cn=hr/!d' ~/openldap/Lab_3/gen_dit/automated_user_ldif_generator.ldif  ; sed -i  '$d' ~/openldap/Lab_3/gen_dit/automated_user_ldif_generator.ldif

echo "Modifying Used and Group IDs"
sed -i s/21000/32000/g ~/openldap/Lab_3/gen_dit/gen_dit.py

echo ""
echo ""
echo "Creating users and groups for Sales organization unit"
echo ""
echo ""

~/openldap/Lab_3/gen_dit/gen_dit.py -s ou=sales,dc=example,dc=com -n 10024 >> ~/openldap/Lab_3/gen_dit/automated_user_ldif_generator.ldif ; sed -i  '1,/cn=hr/!d' ~/openldap/Lab_3/gen_dit/automated_user_ldif_generator.ldif  ; sed -i  '$d' ~/openldap/Lab_3/gen_dit/automated_user_ldif_generator.ldif


echo ""
echo ""
echo "Completed"
